# LizPack Publisher — plugin QGIS pour les instances LizPack
# Copyright (C) 2026 GEODONNÉE INC
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et le
# modifier selon les termes de la Licence publique générale GNU publiée par
# la Free Software Foundation, en version 3 ou toute version ultérieure.
#
# Il est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE
# GARANTIE, sans même la garantie implicite de VALEUR MARCHANDE ou
# d'ADÉQUATION À UN USAGE PARTICULIER. Voyez la Licence publique générale
# GNU pour plus de détails.
#
# Vous devriez avoir reçu une copie de la Licence publique générale GNU
# avec ce programme. Si ce n'est pas le cas, voyez <https://www.gnu.org/licenses/>.
"""
api_client.py
─────────────
Connexion HTTP à l'API LIZPACK (File Manager).
Flow en 2 étapes :
  1. authenticate()   → JWT + liste des instances
  2. connect_instance() → valide l'accès à l'instance
"""
import json
from .i18n import tr, tr_serveur, LANGUE
import os
import zipfile
import mimetypes
import uuid
import datetime
import http.client
import ssl
import time
from urllib.parse import urlparse, urlencode

from qgis.PyQt.QtCore import QSettings

from . import journal
from .envoi_worker import EnvoiWorker, est_projet


# ── Changer cette constante pour passer en production ──────────────────────
# ACCEPT : https://acceptapi.lizpack.com
# PROD   : https://api.lizpack.com
API_BASE = 'https://api.lizpack.com'


class LizpackSession:
    """
    Gère la session en 2 étapes :
    1. authenticate()     → JWT + récupère la liste des instances
    2. connect_instance() → valide l'accès et récupère les métadonnées
    """

    def __init__(self):
        self._s             = QSettings()
        self._jeton         = ''
        self._instance_data = {}
        self._instance_id   = None
        self._instance_name = ''
        self._conn           = None   # connexion HTTP persistante
        self.metadata_error  = ''     # dernier echec de lecture des metadonnees
        # Contexte d'equipe : l'identifiant du proprietaire dont on
        # consulte les instances. None = son propre compte.
        self._team_owner_id  = None
        self.memberships     = []     # equipes dont on est membre
        self.permissions     = {}     # ce que le serveur nous autorise

    @property
    def api_base(self):
        return API_BASE

    def _get_conn(self):
        """Retourne une connexion HTTP persistante (keep-alive)."""
        if self._conn is not None:
            return self._conn
        parsed = urlparse(self.api_base)
        ctx = ssl.create_default_context()
        self._conn = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443,
            timeout=300, context=ctx,
        )
        return self._conn

    def _close_conn(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception as e:
                journal.ignorer(e, 'fermeture de la connexion HTTP')
            self._conn = None

    # ──────────────────────────────────────────────────────────────────
    # Étape 1 : authentification
    # ──────────────────────────────────────────────────────────────────

    def authenticate(self, email, password):
        """
        Obtient le JWT et retourne la liste des instances de l'utilisateur.
        Retourne : [{'id': ..., 'name': ..., 'status': ...}, ...]
        """
        self._jeton = self._get_jwt(email, password)
        self.get_memberships()
        return self._get_instances()

    # ──────────────────────────────────────────────────────────────────
    # Étape 2 : connexion à une instance
    # ──────────────────────────────────────────────────────────────────

    def connect_instance(self, instance_id, instance_name):
        """
        Valide l'accès à l'instance via l'API file manager.
        Récupère aussi les métadonnées (PostGIS, etc.) via le legacy endpoint.
        """
        self._instance_id   = instance_id
        self._instance_name = instance_name

        # Valider l'accès en listant les fichiers (déclenche config SFTP auto côté serveur)
        self._api('GET', f'/api/instances/{instance_id}/files/', params={'path': '/'})

        # Récupérer les métadonnées (PostGIS) — best effort, pas bloquant.
        # L'echec n'empeche pas de travailler sur les fichiers, mais il prive
        # l'onglet PostGIS de ses identifiants ET la publication de sa
        # reecriture des connexions. Il doit donc se voir, pas disparaitre.
        self.metadata_error = ''
        try:
            self._instance_data = self._api('GET', f'/api/infra/lizpack/{instance_id}')
        except Exception as e:
            self._instance_data = {}
            self.metadata_error = str(e)

    def logout(self):
        self._close_conn()
        self._team_owner_id = None
        self.memberships    = []
        self.permissions    = {}
        self._jeton         = ''
        self._instance_data = {}
        self._instance_id   = None
        self._instance_name = ''

    def peut(self, quoi, defaut=True):
        """Le serveur nous autorise-t-il cette action ?

        En l'absence de reponse — serveur plus ancien, compte personnel —
        on ne bride rien : c'est le serveur qui tranche, pas le plugin.
        """
        if not self.permissions:
            return defaut
        return bool(self.permissions.get(quoi, defaut))

    def is_authenticated(self):
        """JWT obtenu."""
        return bool(self._jeton)

    def is_connected(self):
        """JWT + instance sélectionnée."""
        return bool(self._jeton and self._instance_id)

    @property
    def instance_name(self):
        return self._instance_name

    @property
    def instance_id(self):
        return self._instance_id

    # ──────────────────────────────────────────────────────────────────
    # Opérations fichiers (HTTP)
    # ──────────────────────────────────────────────────────────────────

    def list_files(self, api_path='/'):
        """
        Liste les fichiers/dossiers à un chemin donné.
        Retourne : [{'id': int, 'name': str, 'size': int,
                     'modified': float, 'api_path': str, 'is_dir': bool}]
        """
        items = self._api(
            'GET',
            f'/api/instances/{self._instance_id}/files/',
            params={'path': api_path},
        )
        if not isinstance(items, list):
            items = []

        results = []
        for item in items:
            # Convertir modified_at ISO → timestamp unix
            ts = 0.0
            raw = item.get('modified_at') or item.get('modified') or ''
            if raw:
                try:
                    ts = datetime.datetime.fromisoformat(
                        str(raw).replace('Z', '+00:00')
                    ).timestamp()
                except Exception as e:
                    journal.ignorer(e, f'date illisible sur {item.get("name")}')

            results.append({
                'id':       item['id'],
                'name':     item['name'],
                'size':     item.get('size') or 0,
                'modified': ts,
                'api_path': item['path'],
                'is_dir':   item.get('is_folder', False),
                # Le serveur compte les elements d'un dossier sur le disque
                # pendant qu'il le liste, sur une connexion deja ouverte.
                'enfants':  item.get('children_count'),
            })
        return results

    def download(self, file_id):
        """Télécharge un fichier par ID. Retourne bytes."""
        return self._api_raw(
            'GET',
            f'/api/instances/{self._instance_id}/files/{file_id}/download/',
        )

    def download_folder_zip(self, ids, zip_name='projet.zip'):
        """Recupere plusieurs fichiers ou dossiers en une seule archive.

        Le serveur parcourt lui-meme les sous-dossiers et applique aux
        projets la meme restauration que sur un telechargement unitaire.
        Retourne les octets du zip.
        """
        data = json.dumps({'ids': ids, 'zip_name': zip_name}).encode()
        return self._request(
            'POST',
            f'/api/instances/{self._instance_id}/files/create_zip/',
            body=data,
            extra_headers={'Content-Type': 'application/json', 'Accept': '*/*'},
            raw=True,
        )

    def _list_files_cached(self, parent_path):
        """Liste avec cache par session de téléchargement (évite les appels répétés)."""
        cache = getattr(self, '_dir_cache', None)
        if cache is None:
            cache = {}
            self._dir_cache = cache
        key = parent_path.rstrip('/') or '/'
        if key not in cache:
            cache[key] = self.list_files(key)
        return cache[key]

    def clear_cache(self):
        """Vide le cache de listings."""
        self._dir_cache = {}

    def download_by_path(self, server_path):
        """
        Télécharge un fichier par chemin serveur (ex: /qgis/data/france.shp).
        Résout l'ID via listing du dossier parent (cache), puis télécharge.
        """
        server_path = server_path.rstrip('/')
        parts  = server_path.split('/')
        fname  = parts[-1]
        parent = '/'.join(parts[:-1])
        if not parent:
            parent = '/'
        if not parent.endswith('/'):
            parent += '/'

        items = self._list_files_cached(parent)
        for item in items:
            if item['name'] == fname and not item['is_dir']:
                return self.download(item['id'])
        raise Exception(tr('Fichier introuvable : {0}', server_path))

    def upload_file(self, local_path, api_path):
        """Envoie un fichier local vers api_path (chemin absolu, ex: /mon/dossier/fichier.qgs).
        Lève une exception si le serveur refuse le fichier (validation QGS, extension bloquée…).
        """
        parts = api_path.strip('/').split('/')
        parent = ('/' + '/'.join(parts[:-1])) if parts[:-1] else '/'
        self._envoyer_entrees([(local_path, parts[-1])], parent)

    @staticmethod
    def _human_size(nbytes):
        for unit in ('o', 'Ko', 'Mo', 'Go'):
            if abs(nbytes) < 1024:
                return f'{nbytes:.1f} {unit}'
            nbytes /= 1024
        return f'{nbytes:.1f} To'

    def upload_batch(self, file_entries, parent_path, progress_cb=None):
        """Envoie des fichiers.

        file_entries : list[(local_path, rel_path)]
        parent_path  : dossier parent sur le serveur (ex: '/')
        progress_cb  : callback(current, total, texte)
        """
        if not file_entries:
            return 0
        return self._envoyer_entrees(list(file_entries), parent_path, progress_cb)

    def _envoyer_entrees(self, entrees, parent_path, progress_cb=None):
        """Les données vont directement au serveur de l'instance quand il les
        sert (envoi_worker.py : fichiers à jour ignorés, blocs changés seuls,
        compression, reprise) ; sinon au central, en requêtes courtes. Les
        projets QGIS passent toujours par le central, qui les valide, et
        partent après leurs données."""
        projets = [e for e in entrees if est_projet(e[1])]
        donnees = [e for e in entrees if not est_projet(e[1])]
        envoi = EnvoiWorker.ouvrir(self) if donnees else None
        echecs = 0
        try:
            if donnees:
                if envoi:
                    envoi.envoyer(parent_path, donnees, progress_cb)
                else:
                    self._envoyer_central(donnees, parent_path, progress_cb)
            if projets:
                if progress_cb:
                    progress_cb(len(entrees) - len(projets), len(entrees),
                                tr('Validation et envoi de {0} projet(s)…', len(projets)))
                self._envoyer_central(projets, parent_path, None)
        except Exception:
            echecs = 1
            raise
        finally:
            if envoi:
                envoi.remettre_mesure(echecs)
        return len(entrees)

    # Une requête qui dure plus d'une minute et demie environ est coupée en
    # route : vers le central, les lots restent petits, et un gros fichier
    # part par morceaux.
    LOT_CENTRAL = 8 * 1024 * 1024

    def _envoyer_central(self, entrees, parent_path, progress_cb=None):
        total, fait = len(entrees), 0
        lot, octets = [], 0

        def vider():
            nonlocal lot, octets, fait
            if not lot:
                return
            file_list = []
            for local_path, rel_path in lot:
                with open(local_path, 'rb') as f:
                    file_list.append((os.path.basename(rel_path), f.read(), rel_path))
            resp = self._api_multipart(
                f'/api/instances/{self._instance_id}/files/upload_file/',
                fields={'parent_path': parent_path}, files={}, file_list=file_list,
            )
            self._lever_si_bloque(resp)
            fait += len(lot)
            if progress_cb:
                progress_cb(fait, total, tr('{0} / {1} fichier(s) envoyé(s)', fait, total))
            lot, octets = [], 0

        for local_path, rel_path in entrees:
            taille = os.path.getsize(local_path)
            if taille > self.LOT_CENTRAL:
                vider()
                if progress_cb:
                    progress_cb(fait, total, f'{os.path.basename(rel_path)} ({self._human_size(taille)})…')
                self._envoyer_central_par_morceaux(local_path, rel_path, parent_path)
                fait += 1
                continue
            if octets + taille > self.LOT_CENTRAL or len(lot) >= 200:
                vider()
            lot.append((local_path, rel_path))
            octets += taille
        vider()

    def _envoyer_central_par_morceaux(self, local_path, rel_path, parent_path):
        base = f'/api/instances/{self._instance_id}/files'
        d = self._api('POST', f'{base}/upload_init/', data=json.dumps({
            'file_name': os.path.basename(rel_path), 'file_size': os.path.getsize(local_path),
            'file_path': rel_path, 'parent_path': parent_path, 'compressed': False,
        }).encode())
        identifiant = d['upload_id']
        with open(local_path, 'rb') as f:
            i = 0
            while True:
                morceau = f.read(self.LOT_CENTRAL)
                if not morceau and i:
                    break
                frontiere = uuid.uuid4().hex
                entete = (
                    f'--{frontiere}\r\nContent-Disposition: form-data; name="upload_id"\r\n\r\n{identifiant}\r\n'
                    f'--{frontiere}\r\nContent-Disposition: form-data; name="chunk_index"\r\n\r\n{i}\r\n'
                    f'--{frontiere}\r\nContent-Disposition: form-data; name="chunk"; filename="chunk_{i}"\r\n'
                    f'Content-Type: application/octet-stream\r\n\r\n'
                )
                corps = entete.encode() + morceau + f'\r\n--{frontiere}--\r\n'.encode()
                for essai in range(4):
                    try:
                        self._request('POST', f'{base}/upload_chunk/', body=corps, extra_headers={
                            'Content-Type': f'multipart/form-data; boundary={frontiere}',
                            'Accept': 'application/json'})
                        break
                    except Exception:
                        if essai == 3:
                            raise
                        time.sleep(2 ** essai)
                i += 1
                if not morceau:
                    break
        resp = self._api('POST', f'{base}/upload_finalize/', data=json.dumps({'upload_id': identifiant}).encode())
        self._lever_si_bloque(resp)

    @staticmethod
    def _lever_si_bloque(resp):
        if resp and isinstance(resp, dict):
            blocked = resp.get('blocked_files', [])
            if blocked:
                reasons = []
                for bf in blocked:
                    msg = f"{bf.get('name', '?')} : {bf.get('reason', 'Refusé')}"
                    details = bf.get('details', [])
                    if details:
                        msg += '\n  - ' + '\n  - '.join(details)
                    reasons.append(msg)
                raise Exception('\n'.join(reasons))

    def _ensure_remote_dir(self, remote_path):
        """S'assure qu'un dossier distant existe en BDD.
        Crée récursivement les dossiers manquants depuis la racine.
        Utilise le cache pour éviter les appels répétés.
        """
        parts = [p for p in remote_path.strip('/').split('/') if p]
        current = '/'
        for part in parts:
            try:
                items = self._list_files_cached(current)
                exists = any(
                    i['name'] == part and i['is_dir'] for i in items
                )
            except Exception:
                exists = False

            if not exists:
                try:
                    self.create_folder(part, current)
                    # Invalider le cache du parent pour le prochain appel
                    self._dir_cache.pop(current.rstrip('/') or '/', None)
                except Exception as e:
                    # Le serveur recree les dossiers parents a l'envoi : un
                    # echec ici n'empeche pas l'operation d'aboutir.
                    journal.ignorer(e, f'creation du dossier distant {part}')

            current = current.rstrip('/') + '/' + part

    def upload_folder(self, local_folder, api_dest, progress_cb=None):
        """Envoie un dossier entier, sous-dossiers compris."""
        self.clear_cache()
        folder_name = os.path.basename(local_folder)
        remote_root = api_dest.rstrip('/') + '/' + folder_name

        # Le dossier racine existe même vide
        self._ensure_remote_dir(remote_root)

        entries = []
        for root, dirs, files in os.walk(local_folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
            for fname in files:
                if fname.startswith('.'):
                    continue
                local = os.path.join(root, fname)
                rel = folder_name + '/' + os.path.relpath(local, local_folder).replace('\\', '/')
                entries.append((local, rel))
        if not entries:
            return 0
        return self._envoyer_entrees(entries, api_dest, progress_cb)

    def replace_file(self, local_path, api_path):
        """Remplace (ou crée) un fichier distant."""
        self.upload_file(local_path, api_path)

    def delete_file(self, file_id):
        """Supprime un fichier ou dossier par ID (DELETE → 204)."""
        self._api('DELETE', f'/api/instances/{self._instance_id}/files/{file_id}/')

    def create_folder(self, name, parent_path='/'):
        """Crée un dossier. Retourne les métadonnées du dossier créé."""
        data = json.dumps({'name': name, 'parent_path': parent_path}).encode()
        return self._api('POST', f'/api/instances/{self._instance_id}/files/create_folder/', data=data)

    def rename_file(self, file_id, new_name):
        """Renomme un fichier ou dossier."""
        data = json.dumps({'new_name': new_name}).encode()
        return self._api('PATCH', f'/api/instances/{self._instance_id}/files/{file_id}/rename/', data=data)

    def copy_files(self, file_ids, destination_path):
        """Copie des fichiers/dossiers vers un dossier destination."""
        data = json.dumps({'ids': file_ids, 'destination_path': destination_path}).encode()
        return self._api('POST', f'/api/instances/{self._instance_id}/files/copy/', data=data)

    def move_files(self, file_ids, destination_path):
        """Déplace des fichiers/dossiers vers un dossier destination."""
        data = json.dumps({'ids': file_ids, 'destination_path': destination_path}).encode()
        return self._api('POST', f'/api/instances/{self._instance_id}/files/move/', data=data)

    def diagnostiquer_base(self, tables=None):
        """Demande au serveur le diagnostic de la base de l'instance.

        Le diagnostic vit desormais cote LizPack : deux implementations du
        meme controle finissaient par diverger, et le plugin ne pourrait de
        toute facon pas diagnostiquer sans le serveur, dont il tient les
        identifiants de la base.

        Rend la liste des signalements ; chacun porte sa commande SQL isolee,
        que le plugin execute en se connectant en direct.
        """
        corps = json.dumps({'tables': tables} if tables else {}).encode()
        reponse = self._api(
            'POST',
            f'/api/instances/{self._instance_id}/files/diagnose_database/',
            data=corps,
        )
        if not isinstance(reponse, dict):
            return []
        return reponse.get('signalements', [])

    def valider_projet(self, local_path=None, file_id=None):
        """Soumet un projet a l'examen du serveur, sans rien publier.

        Le serveur rend le meme rapport que celui du site : signalements
        classes par gravite, plus le verdict sur les connexions
        PostgreSQL, qui conditionne le depot. Rien n'est ecrit : le
        fichier envoye est lu en memoire puis abandonne.

        Un `.qgz` est une archive ; le validateur attend le projet
        lui-meme, on en extrait donc le `.qgs`.
        """
        chemin = f'/api/instances/{self._instance_id}/files/validate_project/'
        if not local_path:
            data = json.dumps({'file_id': file_id}).encode()
            return self._api('POST', chemin, data=data)

        nom = os.path.basename(local_path)
        if nom.lower().endswith('.qgz'):
            with zipfile.ZipFile(local_path) as archive:
                internes = [n for n in archive.namelist()
                            if n.lower().endswith('.qgs')]
                if not internes:
                    raise Exception(tr("Ce .qgz ne contient aucun projet .qgs."))
                contenu = archive.read(internes[0])
            nom = nom[:-4] + '.qgs'
        else:
            with open(local_path, 'rb') as f:
                contenu = f.read()

        return self._api_multipart(chemin, fields={}, files={'file': (nom, contenu)})

    def get_postgis_uri(self):
        """Retourne les credentials PostGIS pour connexion externe (depuis QGIS Desktop)."""
        d = self._instance_data
        return {
            'host':     d.get('db_host') or d.get('server_ip', ''),
            'port':     str(d.get('db_port') or 5432),
            'dbname':   d.get('db_name', ''),
            'user':     d.get('db_user', ''),
            'password': d.get('db_password', ''),
        }

    def get_postgis_internal(self):
        """Retourne les credentials PostGIS internes (réseau Docker du serveur)."""
        d = self._instance_data
        return {
            'host':     d.get('db_internal_host') or d.get('db_host', ''),
            'port':     str(d.get('db_internal_port') or d.get('db_port') or 5432),
            'dbname':   d.get('db_name', ''),
            'user':     d.get('db_user', ''),
            'password': d.get('db_password', ''),
        }

    # ──────────────────────────────────────────────────────────────────
    # Helpers privés — API
    # ──────────────────────────────────────────────────────────────────

    def _get_jwt(self, email, password):
        data = json.dumps({'email': email, 'password': password}).encode()
        resp = self._api('POST', '/api/auth/jwt/create/', data=data, auth=False)
        if 'access' not in resp:
            raise Exception(tr('Identifiants incorrects.'))
        return resp['access']

    def _get_instances(self):
        resp = self._api('GET', '/api/infra/my-instances/')
        if isinstance(resp, list):
            self.permissions = {}
            return resp
        # Le serveur dit avec la liste ce qu'il nous autorise a faire. Ne
        # pas le lire revenait a proposer des actions qu'il refusera.
        self.permissions = resp.get('permissions', {}) or {}
        return resp.get('instances', resp.get('results', []))

    # ── Transport HTTP (connexion persistante keep-alive) ────────────

    @property
    def team_owner_id(self):
        return self._team_owner_id

    def set_team_context(self, owner_id):
        """Bascule vers l'espace d'un autre proprietaire, ou revient au sien.

        Le serveur lit l'en-tete X-Team-Owner et verifie l'adhesion : le
        plugin n'accorde rien de lui-meme, il demande.
        """
        self._team_owner_id = owner_id
        self._instance_data = {}
        self.clear_cache()

    def get_memberships(self):
        """Les equipes dont l'utilisateur est membre actif."""
        try:
            resp = self._api('GET', '/api/team/memberships/')
        except Exception:
            # Un serveur plus ancien n'expose pas cet endpoint : on reste
            # simplement sur son propre compte.
            return []
        self.memberships = (resp or {}).get('memberships', []) or []
        return self.memberships

    def _base_headers(self):
        return {
            'User-Agent':    'Mozilla/5.0 (compatible; LizpackPublisher/1.0; QGIS plugin)',
            'Origin':        self.api_base,
            'Referer':       self.api_base + '/',
            'Authorization': f'JWT {self._jeton}',
            'Connection':    'keep-alive',
            # Le serveur LizPack répond dans cette langue (messages d'erreur).
            'Accept-Language': LANGUE,
        }

    def _base_headers_avec_equipe(self):
        entetes = self._base_headers()
        if self._team_owner_id:
            entetes['X-Team-Owner'] = str(self._team_owner_id)
        return entetes

    def _request(self, method, path, body=None, extra_headers=None, raw=False):
        """Requête HTTP via connexion persistante. Reconnecte auto si coupée."""
        conn = self._get_conn()
        hdrs = self._base_headers_avec_equipe()
        if extra_headers:
            hdrs.update(extra_headers)

        for attempt in range(2):
            try:
                conn.request(method, path, body=body, headers=hdrs)
                resp = conn.getresponse()
                data = resp.read()

                if 200 <= resp.status < 300:
                    if raw:
                        return data
                    return json.loads(data.decode()) if data.strip() else None

                # Erreur HTTP — parser le message
                try:
                    d = json.loads(data.decode())
                    # « detail » : le serveur LizPack ; « error » : le portail entreprise.
                    msg = d.get('detail') or d.get('error') or d
                    if isinstance(msg, dict):
                        msg = str(msg)
                    msg = tr_serveur(msg)
                except Exception:
                    lines = [ln.strip() for ln in data.decode(errors='replace').splitlines()
                             if ln.strip() and not ln.strip().startswith('<')]
                    msg = lines[0] if lines else f'HTTP {resp.status}'
                # Un 405 signifie que cette action n'existe pas sur le
                # serveur interroge. Le dire a l'utilisateur en nommant la
                # route, ou en parlant de version du backend, l'inquiete
                # sans l'aider et expose l'interieur du produit : le detail
                # part dans le journal de QGIS, a l'usage du support.
                if resp.status == 405:
                    journal.ignorer(
                        'route absente : {} {}'.format(method, path),
                        'fonction indisponible sur le serveur')
                    raise Exception(
                        tr("Cette fonctionnalite n'est pas encore disponible "
                        'pour votre instance. Elle arrivera avec une '
                        'prochaine mise a jour de LizPack.')
                    )
                raise Exception(tr('API {0} : {1}', resp.status, msg))

            except Exception as exc:
                is_conn_error = isinstance(exc, (
                    ConnectionError, OSError, http.client.RemoteDisconnected,
                    http.client.CannotSendRequest, http.client.BadStatusLine,
                ))
                if is_conn_error and attempt == 0:
                    self._close_conn()
                    conn = self._get_conn()
                    continue
                raise

    def _api(self, method, path, data=None, auth=True, params=None):
        """Appel JSON générique."""
        if params:
            path += '?' + urlencode(params)
        hdrs = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if not auth:
            hdrs.pop('Authorization', None)
        return self._request(method, path, body=data, extra_headers=hdrs)

    def _api_raw(self, method, path):
        """Retourne les bytes bruts (download de fichier)."""
        return self._request(method, path, extra_headers={'Accept': '*/*'}, raw=True)

    def _api_multipart(self, path, fields, files, file_list=None):
        """Upload multipart/form-data."""
        boundary = uuid.uuid4().hex
        body = b''
        for key, val in fields.items():
            body += f'--{boundary}\r\n'.encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += f'{val}\r\n'.encode()

        if file_list:
            for filename, content, rel_path in file_list:
                mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                body += f'--{boundary}\r\n'.encode()
                body += (
                    f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
                ).encode()
                body += f'Content-Type: {mime}\r\n\r\n'.encode()
                body += content
                body += b'\r\n'
                body += f'--{boundary}\r\n'.encode()
                body += b'Content-Disposition: form-data; name="paths"\r\n\r\n'
                body += f'{rel_path}\r\n'.encode()
        else:
            for key, (filename, content) in files.items():
                mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                body += f'--{boundary}\r\n'.encode()
                body += (
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                ).encode()
                body += f'Content-Type: {mime}\r\n\r\n'.encode()
                body += content
                body += b'\r\n'

        body += f'--{boundary}--\r\n'.encode()

        return self._request('POST', path, body=body, extra_headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Accept':       'application/json',
        })
