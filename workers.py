"""
workers.py
──────────
QThreads non-bloquants pour les opérations longues.
"""
import os
import xml.etree.ElementTree as ET
from qgis.PyQt.QtCore import QThread, pyqtSignal


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


class UploadFolderWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error    = pyqtSignal(str)

    def __init__(self, session, local_folder, remote_folder):
        super().__init__()
        self.session       = session
        self.local_folder  = local_folder
        self.remote_folder = remote_folder

    def run(self):
        try:
            count = self.session.upload_folder(
                self.local_folder, self.remote_folder,
                progress_cb=lambda cur, tot, fname: self.progress.emit(cur, tot, fname),
            )
            self.finished.emit(count)
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

            # 1. Télécharger le fichier projet
            data = self.session.download(self.file_id)
            with open(self.local_path, 'wb') as f:
                f.write(data)
            self.status.emit(f'  ✓ {os.path.basename(self.local_path)} téléchargé')

            # 2. Télécharger les données référencées (uniquement pour .qgs)
            if self.local_path.lower().endswith('.qgs'):
                try:
                    self._download_dependencies(data.decode('utf-8', errors='ignore'))
                except Exception as e:
                    self.status.emit(f'Avertissement dépendances : {e}')

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

    def _download_dependencies(self, qgs_xml):
        """
        Parse le XML du .qgs, liste le dossier serveur UNE FOIS,
        puis télécharge tous les fichiers nécessaires par ID (pas de listing répété).
        """
        try:
            root = ET.fromstring(qgs_xml)
        except ET.ParseError:
            return

        local_dir  = os.path.dirname(self.local_path)
        srv_parts  = self.server_path.rstrip('/').split('/')
        server_dir = '/'.join(srv_parts[:-1])
        if not server_dir:
            server_dir = '/'

        # 1. Collecter tous les fichiers nécessaires depuis le .qgs
        needed = set()
        for elem in root.iter('datasource'):
            raw = (elem.text or '').strip()
            if not raw:
                continue
            rel = self._extract_relative_path(raw)
            if not rel:
                continue
            needed.add(rel)
            # Compagnons shapefile
            if rel.lower().endswith('.shp'):
                base = rel[:-4]
                for ext in self._SHP_COMPANIONS:
                    needed.add(base + ext)

        for elem in root.iter('styleURI'):
            raw = (elem.text or '').strip()
            rel = self._extract_relative_path(raw)
            if rel:
                needed.add(rel)

        if not needed:
            return

        # 2. Lister le dossier serveur UNE FOIS → map nom→ID
        try:
            items = self.session._list_files_cached(server_dir)
        except Exception:
            items = []
        name_to_id = {it['name']: it['id'] for it in items if not it['is_dir']}

        # 3. Télécharger chaque fichier par son ID (pas de listing supplémentaire)
        self.status.emit(f'  {len(needed)} dépendance(s) à télécharger…')
        for rel in sorted(needed):
            fname = os.path.basename(rel)
            local_file = os.path.join(local_dir, rel.replace('/', os.sep))
            fid = name_to_id.get(fname)

            if fid is None:
                ext = os.path.splitext(fname)[1].lower()
                if ext in self._SHP_CRITICAL:
                    self.status.emit(f'  ⚠ {fname} MANQUANT sur le serveur')
                continue

            try:
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                data = self.session.download(fid)
                if not data:
                    raise Exception('Contenu vide')
                with open(local_file, 'wb') as f:
                    f.write(data)
                self.status.emit(f'  ↳ {fname} ({len(data)} octets)')
            except Exception as e:
                ext = os.path.splitext(fname)[1].lower()
                if ext in self._SHP_CRITICAL:
                    self.status.emit(f'  ⚠ {fname} ERREUR — {e}')

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

    def _fetch(self, server_path, local_path, silent=False):
        """Télécharge un fichier serveur → local. Crée les dossiers si besoin.
        Retourne True si le fichier a été téléchargé, False sinon.
        """
        fname = os.path.basename(server_path)
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            data = self.session.download_by_path(server_path)
            if not data:
                raise Exception('Contenu vide')
            with open(local_path, 'wb') as f:
                f.write(data)
            self.status.emit(f'  ↳ {fname} ({len(data)} octets)')
            return True
        except Exception as e:
            # Les fichiers compagnons critiques ne doivent PAS être silencieux
            ext = os.path.splitext(fname)[1].lower()
            if ext in self._SHP_CRITICAL:
                self.status.emit(f'  ⚠ {fname} MANQUANT — {e}')
            elif not silent:
                self.status.emit(f'  ↳ {fname} introuvable (ignoré)')
            return False

    def _validate_download(self):
        """Vérifie que tous les fichiers référencés dans le .qgs existent localement."""
        missing = []
        if not self.local_path.lower().endswith('.qgs'):
            return missing

        try:
            with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
                qgs_xml = f.read()
            root = ET.fromstring(qgs_xml)
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

            # Réécrire les datasources PostGIS si c'est un .qgs
            if self.local_path.lower().endswith('.qgs'):
                try:
                    upload_path = self._rewrite_pg_datasources()
                except Exception:
                    upload_path = self.local_path

            # 1. Uploader le .qgs (réécrit ou original)
            self.session.replace_file(upload_path, self.api_path)

            # Nettoyer le fichier temporaire
            if upload_path != self.local_path:
                try:
                    os.remove(upload_path)
                except Exception:
                    pass

            # 2. Uploader le .qgs.cfg (config Lizmap) s'il existe
            base = self.local_path
            for cfg_ext in ('.cfg', '.qgs.cfg'):
                cfg_local = base + cfg_ext if cfg_ext == '.cfg' else base + '.cfg'
                if os.path.isfile(cfg_local):
                    cfg_api = self.api_path + '.cfg'
                    self.session.replace_file(cfg_local, cfg_api)
                    break

            # 3. Uploader les fichiers de données locales référencés
            if self.local_path.lower().endswith('.qgs'):
                self._upload_local_dependencies(local_dir, api_dir)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def _upload_local_dependencies(self, local_dir, api_dir):
        """Upload les fichiers de données locales (shapefiles, gpkg, etc.)
        référencés par le projet .qgs."""
        try:
            with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
                qgs_xml = f.read()
            root = ET.fromstring(qgs_xml)
        except Exception:
            return

        uploaded = set()
        for elem in root.iter('datasource'):
            raw = (elem.text or '').strip()
            if not raw:
                continue
            rel = DownloadProjectWorker._extract_relative_path(raw)
            if not rel or rel in uploaded:
                continue

            local_file = os.path.join(local_dir, rel.replace('/', os.sep))
            if not os.path.isfile(local_file):
                continue

            uploaded.add(rel)
            api_path = api_dir.rstrip('/') + '/' + rel
            try:
                self.session.replace_file(local_file, api_path)
            except Exception:
                pass

            # Compagnons shapefile
            if rel.lower().endswith('.shp'):
                base_rel = rel[:-4]
                for ext in ('.shx', '.dbf', '.prj', '.cpg', '.qix', '.qml', '.qpj'):
                    comp_rel = base_rel + ext
                    comp_local = os.path.join(local_dir, comp_rel.replace('/', os.sep))
                    if os.path.isfile(comp_local) and comp_rel not in uploaded:
                        uploaded.add(comp_rel)
                        try:
                            self.session.replace_file(
                                comp_local,
                                api_dir.rstrip('/') + '/' + comp_rel,
                            )
                        except Exception:
                            pass

    def _rewrite_pg_datasources(self):
        """Réécrit les connexions PostGIS du .qgs pour utiliser
        les credentials internes de l'instance (réseau Docker).
        Retourne le chemin du fichier modifié (temp).
        """
        import re, tempfile

        d = self.session._instance_data
        if not d:
            return self.local_path

        # Credentials internes du serveur
        target_host = d.get('db_internal_host') or d.get('db_host') or ''
        target_port = str(d.get('db_internal_port') or d.get('db_port') or 5432)
        target_db   = d.get('db_name', '')
        target_user = d.get('db_user', '')
        target_pass = d.get('db_password', '')

        if not target_host or not target_user:
            return self.local_path

        with open(self.local_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Réécrire chaque datasource PostGIS
        def rewrite_pg(match):
            ds = match.group(0)
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
