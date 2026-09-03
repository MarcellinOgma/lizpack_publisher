"""
workers.py
──────────
QThreads non-bloquants pour les opérations longues.
"""
import io
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from qgis.PyQt.QtCore import QThread, pyqtSignal

try:
    from defusedxml.ElementTree import fromstring as _defused_fromstring
except ImportError:      # defusedxml n'est pas fourni avec QGIS
    _defused_fromstring = None


def parse_qgs_xml(xml_text):
    """Parse le XML d'un .qgs venant du serveur, sans exposer QGIS aux
    attaques XML (entites externes / XXE, billion laughs).

    Utilise defusedxml s'il est disponible, sinon un parseur expat durci.
    NB : la DOCTYPE reste acceptee — QGIS en ecrit une dans chaque .qgs
    (<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>) ; ce sont
    les DECLARATIONS D'ENTITES qui sont refusees, et c'est par elles que
    passent XXE et les bombes d'expansion.
    Leve ET.ParseError comme ET.fromstring.
    """
    if _defused_fromstring is not None:
        try:
            return _defused_fromstring(xml_text)
        except ET.ParseError:
            raise
        except Exception as exc:
            # DefusedXmlException (entite interdite) -> traite comme un XML invalide
            raise ET.ParseError(str(exc))

    # Pas de defusedxml : on pilote expat directement, car les handlers
    # poses sur ET.XMLParser().parser sont ignores par l'accelerateur C.
    import xml.parsers.expat

    builder = ET.TreeBuilder()
    # separateur "}" + prefixe "{" : memes noms qualifies que ET.fromstring
    expat = xml.parsers.expat.ParserCreate(None, '}')

    def _forbid_entity(*_args, **_kwargs):
        raise ET.ParseError("Declaration d'entite XML interdite")

    expat.EntityDeclHandler = _forbid_entity
    expat.UnparsedEntityDeclHandler = _forbid_entity
    expat.ExternalEntityRefHandler = lambda *_a, **_k: False
    expat.StartElementHandler = lambda tag, attrs: builder.start(
        ('{' + tag) if '}' in tag else tag,
        {(('{' + k) if '}' in k else k): v for k, v in attrs.items()},
    )
    expat.EndElementHandler = lambda tag: builder.end(
        ('{' + tag) if '}' in tag else tag
    )
    expat.CharacterDataHandler = builder.data

    try:
        expat.Parse(xml_text, True)
    except xml.parsers.expat.ExpatError as exc:
        raise ET.ParseError(str(exc))

    return builder.close()


class ListFilesWorker(QThread):
    """Liste les fichiers d'un dossier distant de façon non-bloquante."""
    finished = pyqtSignal(list)   # [{'id', 'name', 'size', 'modified', 'api_path', 'is_dir'}]
    error    = pyqtSignal(str)

    def __init__(self, session, api_path='/'):
        super().__init__()
        self.session  = session
        self.api_path = api_path

    def run(self):
        try:
            files = self.session.list_files(self.api_path)
            self.finished.emit(files)
        except Exception as e:
            self.error.emit(str(e))


class LoginWorker(QThread):
    """Étape 1 : obtient le JWT et retourne la liste des instances."""
    finished = pyqtSignal(list)   # liste d'instances [{id, name, status}, ...]
    error    = pyqtSignal(str)

    def __init__(self, session, email, password):
        super().__init__()
        self.session  = session
        self.email    = email
        self.password = password

    def run(self):
        try:
            instances = self.session.authenticate(self.email, self.password)
            self.finished.emit(instances)
        except Exception as e:
            self.error.emit(str(e))


class ListeInstancesWorker(QThread):
    """Redemande la liste des instances, sans refaire l'authentification.

    Sert au changement d'espace de travail : le jeton reste valable, seul
    le contexte d'equipe change.
    """
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            self.finished.emit(self.session._get_instances())
        except Exception as e:
            self.error.emit(str(e))


class ConnectInstanceWorker(QThread):
    """Étape 2 : récupère les credentials SFTP et teste la connexion."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, session, instance_id, instance_name):
        super().__init__()
        self.session       = session
        self.instance_id   = instance_id
        self.instance_name = instance_name

    def run(self):
        try:
            self.session.connect_instance(self.instance_id, self.instance_name)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class DownloadProjectWorker(QThread):
    """
    Télécharge un projet .qgs/.qgz ET toutes ses données référencées
    (shapefiles, rasters, GeoJSON, QML…) depuis le serveur.
    """
    finished = pyqtSignal(str)
    status   = pyqtSignal(str)   # messages de progression
    error    = pyqtSignal(str)

    # Extensions compagnes d'un shapefile
    _SHP_COMPANIONS = ('.shx', '.dbf', '.prj', '.cpg', '.qix', '.sbn', '.sbx', '.qml', '.qpj')

    def __init__(self, session, file_id, local_path, server_path):
        super().__init__()
        self.session     = session
        self.file_id     = file_id
        self.local_path  = local_path   # chemin local destination du .qgs
        self.server_path = server_path  # chemin serveur du .qgs (ex: /qgis/projet.qgs)

    def run(self):
        try:
            self.session.clear_cache()
            srv_parts  = self.server_path.rstrip('/').split('/')
            server_dir = '/'.join(srv_parts[:-1]) or '/'
            local_dir  = os.path.dirname(self.local_path)

            # 1. Voie rapide : tout le dossier en UNE requete.
            if not self._rapatrier_en_archive(server_dir, local_dir):
                # 2. Repli fichier par fichier si le serveur ne sait pas
                #    produire d'archive, ou si elle n'est pas exploitable.
                data = self.session.download(self.file_id)
                with open(self.local_path, 'wb') as f:
                    f.write(data)
                self.status.emit(f'  ✓ {os.path.basename(self.local_path)} téléchargé')
                try:
                    self.session.clear_cache()
                    n = self._miroir_dossier(server_dir, local_dir)
                    self.status.emit(f'  {n} fichier(s) rapatrié(s) depuis {server_dir}')
                except Exception as e:
                    self.status.emit(f'Avertissement arborescence : {e}')

            # 3. Valider l'intégrité du téléchargement
            missing = self._validate_download()
            if missing:
                self.status.emit(
                    f'⚠ {len(missing)} fichier(s) manquant(s) :\n'
                    + '\n'.join(f'  · {m}' for m in missing)
                )

            self.finished.emit(self.local_path)
        except Exception as e:
            self.error.emit(str(e))

    def _rapatrier_en_archive(self, server_dir, local_dir):
        """Rapatrie le dossier entier en une seule requete.

        Fichier par fichier, il fallait un aller-retour HTTP par fichier et
        un par sous-dossier : sur un projet et ses donnees, la latence
        pesait plus lourd que les octets transferes. Le serveur sait
        assembler l'archive lui-meme, en parcourant les sous-dossiers et en
        restaurant les projets comme sur un telechargement unitaire.

        Retourne False si l'archive n'a pas pu etre obtenue ou exploitee :
        l'appelant retombe alors sur la methode fichier par fichier.
        """
        try:
            items = self.session.list_files(server_dir)
        except Exception as e:
            self.status.emit(f'  dossier illisible ({e})')
            return False

        ids = [it['id'] for it in items]
        if not ids:
            return False

        self.status.emit(f'  {len(ids)} élément(s) — récupération en une archive…')
        try:
            brut = self.session.download_folder_zip(ids)
        except Exception as e:
            self.status.emit(f'  archive indisponible ({e}) — repli fichier par fichier')
            return False

        if not brut or brut[:2] != b'PK':
            self.status.emit('  réponse inattendue — repli fichier par fichier')
            return False

        prefixe = server_dir.strip('/')
        racine  = os.path.abspath(local_dir)
        ecrits  = 0
        try:
            with zipfile.ZipFile(io.BytesIO(brut)) as archive:
                for nom in archive.namelist():
                    rel = nom
                    if prefixe and rel.startswith(prefixe + '/'):
                        rel = rel[len(prefixe) + 1:]
                    if not rel or rel.endswith('/'):
                        continue

                    cible = os.path.abspath(
                        os.path.join(racine, rel.replace('/', os.sep))
                    )
                    # Une archive peut contenir des chemins remontants : ne
                    # jamais ecrire hors du dossier de destination.
                    if cible != racine and not cible.startswith(racine + os.sep):
                        self.status.emit(f'  ⚠ entrée hors dossier ignorée : {nom}')
                        continue

                    os.makedirs(os.path.dirname(cible), exist_ok=True)
                    with archive.open(nom) as source, open(cible, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
                    ecrits += 1
        except zipfile.BadZipFile as e:
            self.status.emit(f'  archive illisible ({e}) — repli fichier par fichier')
            return False

        if not os.path.isfile(self.local_path):
            self.status.emit('  projet absent de l\'archive — repli fichier par fichier')
            return False

        self.status.emit(f'  {ecrits} fichier(s) rapatrié(s) en une requête')
        return True

    def _miroir_dossier(self, server_dir, local_dir):
        """Recopie le dossier serveur et tous ses sous-dossiers en local.

        Un projet reference ses donnees en relatif, souvent depuis un
        sous-dossier. Rapatrier l'arborescence entiere est le seul moyen
        fiable de rouvrir le projet tel quel : resoudre chemin par chemin
        obligeait a deviner ou chaque fichier se trouve, et manquait tout
        ce qui n'etait pas cite explicitement (qml, index, .qgd...).

        Retourne le nombre de fichiers ecrits.
        """
        ecrits = 0
        a_traiter = [(server_dir, local_dir)]
        vus = set()

        while a_traiter:
            srv, loc = a_traiter.pop(0)
            cle = srv.rstrip('/') or '/'
            if cle in vus:
                continue
            vus.add(cle)

            try:
                items = self.session.list_files(srv)
            except Exception as e:
                self.status.emit(f'  ⚠ dossier {srv} illisible — {e}')
                continue

            os.makedirs(loc, exist_ok=True)
            for it in items:
                cible = os.path.join(loc, it['name'])
                if it['is_dir']:
                    a_traiter.append((it['api_path'], cible))
                    continue
                # Le fichier projet a deja ete ecrit par run()
                if os.path.abspath(cible) == os.path.abspath(self.local_path):
                    continue
                try:
                    contenu = self.session.download(it['id'])
                    with open(cible, 'wb') as f:
                        f.write(contenu)
                    ecrits += 1
                    self.status.emit(f'  ↳ {it["name"]} ({len(contenu)} octets)')
                except Exception as e:
                    self.status.emit(f'  ⚠ {it["name"]} — {e}')

        return ecrits

    @staticmethod
    def _extract_relative_path(src):
        """
        Extrait le chemin relatif d'une datasource si c'est un fichier local.
        Retourne None pour PostGIS, WMS/WFS, URLs, chemins absolus.
        """
        # Nettoyer suffixes OGR : |layername=... ou |subset=...
        clean = src.split('|')[0].strip()

        # Ignorer : connexions PostGIS/DB
        if any(k in clean for k in ("dbname=", "PG:", "host=", "service=", "mysql:")):
            return None
        # Ignorer : URLs et services OWS
        if any(clean.lower().startswith(p) for p in (
            'http://', 'https://', 'wms:', 'wfs:', 'wmts:', 'wcs:',
            'ogc:', 'ftp://', 'memory?', 'virtual:',
        )):
            return None
        # Ignorer : chemins absolus qui ne correspondent pas à un relatif
        if os.path.isabs(clean) and not clean.startswith('./') and not clean.startswith('../'):
            return None

        # Normaliser le chemin relatif
        if clean.startswith('./'):
            clean = clean[2:]
        if not clean:
            return None

        return clean

    # Extensions critiques d'un shapefile (sans lesquelles la couche est cassée)
    _SHP_CRITICAL = ('.shx', '.dbf')

    def _validate_download(self):
        """Vérifie que tous les fichiers référencés dans le .qgs existent localement."""
        missing = []
        if not self.local_path.lower().endswith('.qgs'):
            return missing

        try:
            with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
                qgs_xml = f.read()
            root = parse_qgs_xml(qgs_xml)
        except Exception:
            return missing

        local_dir = os.path.dirname(self.local_path)

        for elem in root.iter('datasource'):
            raw = (elem.text or '').strip()
            if not raw:
                continue
            rel = self._extract_relative_path(raw)
            if not rel:
                continue

            local_file = os.path.join(local_dir, rel.replace('/', os.sep))
            if not os.path.isfile(local_file):
                missing.append(rel)

            # Vérifier les compagnons shapefile critiques
            if rel.lower().endswith('.shp'):
                base = rel[:-4]
                for ext in self._SHP_CRITICAL:
                    companion = base + ext
                    comp_path = os.path.join(local_dir, companion.replace('/', os.sep))
                    if not os.path.isfile(comp_path):
                        missing.append(companion)

        return missing


class SaveSymbologyWorker(QThread):
    """Publie un projet .qgs en réécrivant les connexions PostGIS
    pour qu'elles pointent vers la BDD interne de l'instance."""
    finished = pyqtSignal()
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, session, local_path, api_path):
        super().__init__()
        self.session    = session
        self.local_path = local_path
        self.api_path   = api_path

    def run(self):
        try:
            upload_path = self.local_path
            local_dir = os.path.dirname(self.local_path)
            api_dir   = '/'.join(self.api_path.rstrip('/').split('/')[:-1]) or '/'
            nom_projet = os.path.basename(self.api_path)

            # Réécrire les datasources PostGIS si c'est un .qgs
            if self.local_path.lower().endswith('.qgs'):
                try:
                    upload_path = self._rewrite_pg_datasources()
                except Exception as e:
                    # Publier sans reecriture donne un projet que Lizmap ne
                    # peut pas ouvrir : la panne doit se voir. C'est ce
                    # except, muet jusqu'ici, qui a caché pendant des mois
                    # une AttributeError dans rewrite_pg().
                    upload_path = self.local_path
                    self.status.emit(
                        f'  ⚠ connexions PostGIS NON réécrites ({e}). '
                        'Le projet publié gardera ses adresses locales.'
                    )

            # Tout part en UNE requete. Un envoi par fichier faisait payer la
            # latence autant de fois qu'il y a de couches : sur un projet
            # ordinaire, l'attente venait des aller-retours, pas des octets.
            # Le nom d'arrivee vient du chemin relatif, pas du nom du fichier
            # envoye : le .qgs reecrit, qui porte un nom temporaire, arrive
            # donc bien sous le nom voulu.
            envois = [(upload_path, nom_projet)]

            cfg_local = self.local_path + '.cfg'
            if os.path.isfile(cfg_local):
                envois.append((cfg_local, nom_projet + '.cfg'))

            if self.local_path.lower().endswith('.qgs'):
                envois.extend(self._dependances_locales(local_dir))

            self.status.emit(f'  {len(envois)} fichier(s) à publier…')
            try:
                self.session.upload_batch(
                    envois, api_dir,
                    progress_cb=lambda cur, tot, nom: self.status.emit(f'  {nom}'),
                )
            finally:
                # Nettoyer le .qgs temporaire, meme si l'envoi a echoue
                if upload_path != self.local_path:
                    try:
                        os.remove(upload_path)
                    except Exception:
                        pass

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def _dependances_locales(self, local_dir):
        """Liste les donnees locales que le projet reference.

        Retourne des couples (chemin local, chemin relatif) prets pour un
        envoi groupe. Les fichiers absents du disque sont ignores : une
        couche PostGIS ou un service WMS n'a rien a envoyer.
        """
        try:
            with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
                racine = parse_qgs_xml(f.read())
        except Exception:
            return []

        envois = []
        vus = set()

        def ajouter(rel):
            if rel in vus:
                return
            local = os.path.join(local_dir, rel.replace('/', os.sep))
            if not os.path.isfile(local):
                return
            vus.add(rel)
            envois.append((local, rel))

        for elem in racine.iter('datasource'):
            brut = (elem.text or '').strip()
            if not brut:
                continue
            rel = DownloadProjectWorker._extract_relative_path(brut)
            if not rel:
                continue
            ajouter(rel)
            if rel.lower().endswith('.shp'):
                base = rel[:-4]
                for ext in ('.shx', '.dbf', '.prj', '.cpg', '.qix', '.qml', '.qpj'):
                    ajouter(base + ext)

        return envois

    def _avertir_sans_reecriture(self, raison):
        """Signale qu'un projet part sans que ses connexions soient reecrites.

        Ne le dire que si le projet contient vraiment du PostGIS : sur un
        projet fait de shapefiles, l'absence de reecriture est normale et
        l'avertissement serait du bruit.
        """
        try:
            with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
                contenu = f.read()
        except Exception:
            return
        if 'dbname=' not in contenu:
            return
        self.status.emit(
            f'  ⚠ connexions PostGIS NON réécrites : {raison}. '
            'Lizmap ne pourra pas joindre la base.'
        )

    def _rewrite_pg_datasources(self):
        """Réécrit les connexions PostGIS du .qgs pour utiliser
        les credentials internes de l'instance (réseau Docker).
        Retourne le chemin du fichier modifié (temp).
        """
        import re
        import tempfile

        d = self.session._instance_data
        if not d:
            self._avertir_sans_reecriture(
                "les informations de l'instance n'ont pas été récupérées"
            )
            return self.local_path

        # Credentials internes du serveur
        target_host = d.get('db_internal_host') or d.get('db_host') or ''
        target_port = str(d.get('db_internal_port') or d.get('db_port') or 5432)
        target_db   = d.get('db_name', '')
        target_user = d.get('db_user', '')
        target_pass = d.get('db_password', '')

        if not target_host or not target_user:
            self._avertir_sans_reecriture(
                "l'instance n'expose ni adresse ni utilisateur de base"
            )
            return self.local_path

        with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Réécrire chaque datasource PostGIS.
        # NB : cette fonction recoit le CONTENU de la balise, deja extrait par
        # l'appelant, pas un objet de correspondance. Elle appelait
        # match.group(0) et levait donc AttributeError a chaque projet ; le
        # try/except de l'appelant avalait l'erreur et publiait le projet sans
        # aucune reecriture. La panne etait totale et silencieuse.
        def rewrite_pg(ds):
            # Ne réécrire que si c'est bien une connexion PG
            if 'dbname=' not in ds:
                return ds
            ds = re.sub(r"host=[^\s'\"]+",     f"host={target_host}", ds)
            ds = re.sub(r"port=\d+",           f"port={target_port}", ds)
            ds = re.sub(r"dbname='[^']*'",     f"dbname='{target_db}'", ds)
            # Remplacer ou injecter user
            if re.search(r"user='[^']*'", ds):
                ds = re.sub(r"user='[^']*'", f"user='{target_user}'", ds)
            else:
                ds = re.sub(r"(dbname='[^']*')", rf"\1 user='{target_user}'", ds)
            # Remplacer ou injecter password
            if re.search(r"password='[^']*'", ds):
                ds = re.sub(r"password='[^']*'", f"password='{target_pass}'", ds)
            else:
                ds = re.sub(r"(user='[^']*')", rf"\1 password='{target_pass}'", ds)
            # Supprimer authcfg si présent (on utilise des credentials directs)
            ds = re.sub(r"\s*authcfg=\S+", '', ds)
            return ds

        # Pattern : contenu de <datasource>...</datasource> contenant dbname=
        content = re.sub(
            r'(<datasource>)(.*?)(</datasource>)',
            lambda m: m.group(1) + rewrite_pg(m.group(2)) + m.group(3),
            content,
            flags=re.DOTALL,
        )

        # Sauvegarder dans un fichier temporaire
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.qgs', delete=False, encoding='utf-8',
        )
        tmp.write(content)
        tmp.close()
        return tmp.name


class DeleteWorker(QThread):
    """Supprime une liste de fichiers/dossiers par ID."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, session, file_ids):
        super().__init__()
        self.session  = session
        self.file_ids = file_ids  # list[int]

    def run(self):
        try:
            for fid in self.file_ids:
                self.session.delete_file(fid)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class CreateFolderWorker(QThread):
    """Crée un dossier distant."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, session, name, parent_path):
        super().__init__()
        self.session     = session
        self.name        = name
        self.parent_path = parent_path

    def run(self):
        try:
            self.session.create_folder(self.name, self.parent_path)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class RenameWorker(QThread):
    """Renomme un fichier ou dossier distant."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, session, file_id, new_name):
        super().__init__()
        self.session  = session
        self.file_id  = file_id
        self.new_name = new_name

    def run(self):
        try:
            self.session.rename_file(self.file_id, self.new_name)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class UploadFilesWorker(QThread):
    """Upload plusieurs fichiers locaux vers un dossier distant (batch)."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error    = pyqtSignal(str)

    def __init__(self, session, local_files, dest_path):
        super().__init__()
        self.session     = session
        self.local_files = local_files  # list[str]
        self.dest_path   = dest_path    # chemin serveur destination

    def run(self):
        try:
            entries = [
                (lp, os.path.basename(lp)) for lp in self.local_files
            ]
            count = self.session.upload_batch(
                entries, self.dest_path,
                progress_cb=lambda cur, tot, fn: self.progress.emit(cur, tot, fn),
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class UploadFolderWorker(QThread):
    """Upload un dossier entier via batch (une requête par lot de ~20 Mo)."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error    = pyqtSignal(str)

    def __init__(self, session, local_folder, dest_path):
        super().__init__()
        self.session      = session
        self.local_folder = local_folder
        self.dest_path    = dest_path

    def run(self):
        try:
            count = self.session.upload_folder(
                self.local_folder, self.dest_path,
                progress_cb=lambda cur, tot, fn: self.progress.emit(cur, tot, fn),
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class _FilBase(QThread):
    """Ouvre une connexion psycopg2 vers la base de l'instance."""

    def __init__(self, pg):
        super().__init__()
        self.pg = pg

    def _connexion(self):
        import psycopg2
        return psycopg2.connect(
            host=self.pg['host'], port=self.pg['port'],
            dbname=self.pg['dbname'], user=self.pg['user'],
            password=self.pg['password'], connect_timeout=15,
        )


class DiagnosticDbWorker(_FilBase):
    """Analyse la base sans rien y modifier."""
    finished = pyqtSignal(list)   # [Probleme]
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def run(self):
        connexion = None
        try:
            from .optimisation import diagnostiquer
            self.status.emit('Connexion à la base…')
            connexion = self._connexion()
            curseur = connexion.cursor()
            problemes = diagnostiquer(curseur, journal=self.status.emit)
            curseur.close()
            self.finished.emit(problemes)
        except ImportError:
            self.error.emit(
                'psycopg2 est absent de cette installation de QGIS : '
                "le diagnostic de la base n'est pas disponible."
            )
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if connexion is not None:
                try:
                    connexion.close()
                except Exception:
                    pass


class OptimiserDbWorker(_FilBase):
    """Applique les corrections sures retenues par le diagnostic."""
    finished = pyqtSignal(list, list)   # reussies, echouees
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, pg, problemes):
        super().__init__(pg)
        self.problemes = problemes

    def run(self):
        connexion = None
        try:
            from .optimisation import appliquer
            self.status.emit('Connexion à la base…')
            connexion = self._connexion()
            reussies, echouees = appliquer(
                connexion, self.problemes, journal=self.status.emit,
            )
            self.finished.emit(reussies, echouees)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if connexion is not None:
                try:
                    connexion.close()
                except Exception:
                    pass


class ImportToPostGISWorker(QThread):
    """Importe une couche vectorielle QGIS dans la base PostGIS de l'instance."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, layer, pg_uri, schema, table_name):
        super().__init__()
        self.layer      = layer
        self.pg_uri     = pg_uri      # dict: host, port, dbname, user, password
        self.schema     = schema
        self.table_name = table_name

    def run(self):
        try:
            from qgis.core import QgsVectorLayerExporter, QgsDataSourceUri

            uri = QgsDataSourceUri()
            uri.setConnection(
                self.pg_uri['host'],
                str(self.pg_uri['port']),
                self.pg_uri['dbname'],
                self.pg_uri['user'],
                self.pg_uri['password'],
            )
            uri.setDataSource(self.schema, self.table_name, 'geom')

            error, msg = QgsVectorLayerExporter.exportLayer(
                self.layer,
                uri.uri(False),
                'postgres',
                self.layer.crs(),
                False,
            )

            if error != QgsVectorLayerExporter.NoError:
                raise Exception(msg or f'Erreur export (code {error})')

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
