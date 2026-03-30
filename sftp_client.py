"""
sftp_client.py
──────────────
Connexion HTTP à l'API LIZPACK (File Manager).
Flow en 2 étapes :
  1. authenticate()   → JWT + liste des instances
  2. connect_instance() → valide l'accès à l'instance
"""
import json
import os
import mimetypes
import uuid
import datetime
import http.client
import ssl
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from qgis.PyQt.QtCore import QSettings


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
        self._token         = ''
        self._instance_data = {}
        self._instance_id   = None
        self._instance_name = ''
        self._conn           = None   # connexion HTTP persistante

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
            except Exception:
                pass
            self._conn = None

    # ──────────────────────────────────────────────────────────────────
    # Étape 1 : authentification
    # ──────────────────────────────────────────────────────────────────

    def authenticate(self, email, password):
        """
        Obtient le JWT et retourne la liste des instances de l'utilisateur.
        Retourne : [{'id': ..., 'name': ..., 'status': ...}, ...]
        """
        self._token = self._get_jwt(email, password)
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

        # Récupérer les métadonnées (PostGIS) — best effort, pas bloquant
        try:
            self._instance_data = self._api('GET', f'/api/infra/lizpack/{instance_id}')
        except Exception:
            self._instance_data = {}

    def logout(self):
        self._close_conn()
        self._token         = ''
        self._instance_data = {}
        self._instance_id   = None
        self._instance_name = ''

    def is_authenticated(self):
        """JWT obtenu."""
        return bool(self._token)

    def is_connected(self):
        """JWT + instance sélectionnée."""
        return bool(self._token and self._instance_id)

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
                except Exception:
                    pass

            results.append({
                'id':       item['id'],
                'name':     item['name'],
                'size':     item.get('size') or 0,
                'modified': ts,
                'api_path': item['path'],
                'is_dir':   item.get('is_folder', False),
            })
        return results

    def download(self, file_id):
        """Télécharge un fichier par ID. Retourne bytes."""
        return self._api_raw(
            'GET',
            f'/api/instances/{self._instance_id}/files/{file_id}/download/',
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
        raise Exception(f'Fichier introuvable : {server_path}')

    def upload_file(self, local_path, api_path):
        """Upload un fichier local vers api_path (chemin absolu, ex: /mon/dossier/fichier.qgs).
        Lève une exception si le backend refuse le fichier (validation QGS, extension bloquée…).
        """
        filename    = os.path.basename(local_path)
        parts       = api_path.strip('/').split('/')
        parent_parts = parts[:-1]
        parent      = ('/' + '/'.join(parent_parts)) if parent_parts else '/'

        with open(local_path, 'rb') as f:
            content = f.read()

        resp = self._api_multipart(
            f'/api/instances/{self._instance_id}/files/upload_file/',
            fields={'parent_path': parent},
            files={'files': (filename, content)},
        )

        # Vérifier si le backend a bloqué le fichier
        if resp and isinstance(resp, dict):
            blocked = resp.get('blocked_files', [])
            if blocked:
                reasons = []
                for bf in blocked:
                    name = bf.get('name', filename)
                    reason = bf.get('reason', 'Refusé par le serveur')
                    details = bf.get('details', [])
                    msg = f'{name} : {reason}'
                    if details:
                        msg += '\n  - ' + '\n  - '.join(details)
                    reasons.append(msg)
                raise Exception('\n'.join(reasons))

    @staticmethod
    def _human_size(nbytes):
        for unit in ('o', 'Ko', 'Mo', 'Go'):
            if abs(nbytes) < 1024:
                return f'{nbytes:.1f} {unit}'
            nbytes /= 1024
        return f'{nbytes:.1f} To'

    def upload_batch(self, file_entries, parent_path, progress_cb=None):
        """Upload tous les fichiers en UNE seule requête HTTP (comme le frontend).

        file_entries : list[(local_path, rel_path)]
        parent_path  : dossier parent sur le serveur (ex: '/')
        progress_cb  : callback(current, total, filename_with_size)
        """
        total = len(file_entries)
        if total == 0:
            return 0

        # Lire tous les fichiers et construire le file_list
        file_list = []
        total_size = 0
        for i, (local_path, rel_path) in enumerate(file_entries):
            fname = os.path.basename(local_path)
            fsize = os.path.getsize(local_path)
            total_size += fsize
            if progress_cb:
                progress_cb(i + 1, total, f'Lecture {fname} ({self._human_size(fsize)})')
            with open(local_path, 'rb') as f:
                content = f.read()
            file_list.append((fname, content, rel_path))

        # Envoyer tout en une seule requête
        if progress_cb:
            progress_cb(total, total, f'Envoi de {total} fichier(s) ({self._human_size(total_size)})…')

        resp = self._api_multipart(
            f'/api/instances/{self._instance_id}/files/upload_file/',
            fields={'parent_path': parent_path},
            files={},
            file_list=file_list,
        )

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

        return total

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
                except Exception:
                    pass

            current = current.rstrip('/') + '/' + part

    def upload_folder(self, local_folder, api_dest, progress_cb=None):
        """Upload un dossier entier. Crée l'arborescence distante puis upload les fichiers."""
        self.clear_cache()
        folder_name = os.path.basename(local_folder)
        remote_root = api_dest.rstrip('/') + '/' + folder_name

        # Créer le dossier racine
        self._ensure_remote_dir(remote_root)

        # Collecter les fichiers et sous-dossiers
        entries = []
        # Collecter tous les fichiers avec leurs chemins relatifs
        for root, dirs, files in os.walk(local_folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
            for fname in files:
                if fname.startswith('.'):
                    continue
                local = os.path.join(root, fname)
                # Chemin relatif incluant le nom du dossier racine
                rel = folder_name + '/' + os.path.relpath(local, local_folder).replace('\\', '/')
                entries.append((local, rel))

        if not entries:
            return 0

        # Tout envoyer en UNE seule requête (comme le frontend)
        total = len(entries)
        file_list = []
        total_size = 0
        for i, (local_path, rel_path) in enumerate(entries):
            fname = os.path.basename(local_path)
            fsize = os.path.getsize(local_path)
            total_size += fsize
            if progress_cb:
                progress_cb(i + 1, total, f'Lecture {fname} ({self._human_size(fsize)})')
            with open(local_path, 'rb') as f:
                content = f.read()
            file_list.append((fname, content, rel_path))

        if progress_cb:
            progress_cb(total, total, f'Envoi de {total} fichier(s) ({self._human_size(total_size)})…')

        resp = self._api_multipart(
            f'/api/instances/{self._instance_id}/files/upload_file/',
            fields={'parent_path': api_dest},
            files={},
            file_list=file_list,
        )

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

        return total

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
            raise Exception('Identifiants incorrects.')
        return resp['access']

    def _get_instances(self):
        resp      = self._api('GET', '/api/infra/my-instances/')
        instances = (resp if isinstance(resp, list)
                     else resp.get('instances', resp.get('results', [])))
        return instances

    # ── Transport HTTP (connexion persistante keep-alive) ────────────

    def _base_headers(self):
        return {
            'User-Agent':    'Mozilla/5.0 (compatible; LizpackPublisher/1.0; QGIS plugin)',
            'Origin':        self.api_base,
            'Referer':       self.api_base + '/',
            'Authorization': f'JWT {self._token}',
            'Connection':    'keep-alive',
        }

    def _request(self, method, path, body=None, extra_headers=None, raw=False):
        """Requête HTTP via connexion persistante. Reconnecte auto si coupée."""
        conn = self._get_conn()
        hdrs = self._base_headers()
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
                    msg = json.loads(data.decode()).get('detail') or json.loads(data.decode())
                    if isinstance(msg, dict):
                        msg = str(msg)
                except Exception:
                    lines = [l.strip() for l in data.decode(errors='replace').splitlines()
                             if l.strip() and not l.strip().startswith('<')]
                    msg = lines[0] if lines else f'HTTP {resp.status}'
                raise Exception(f'API {resp.status} : {msg}')

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
                body += f'Content-Disposition: form-data; name="paths"\r\n\r\n'.encode()
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
