# LizPack Publisher — plugin QGIS pour les instances LizPack
# Copyright (C) 2026 GEODONNÉE INC
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et le
# modifier selon les termes de la Licence publique générale GNU publiée par
# la Free Software Foundation, en version 3 ou toute version ultérieure.
# Voyez <https://www.gnu.org/licenses/>.
"""
session_entreprise.py
─────────────────────
La même session que `LizpackSession`, parlant au portail de l'édition
entreprise (serveur installé chez le client) au lieu du serveur LizPack.

Différences avec le mutualisé, toutes absorbées ici pour que le reste du
plugin n'en sache rien :
  - connexion par jeton d'API du portail (« Mon profil > Jetons d'API »),
    envoyé en `Authorization: Bearer` ; ni équipes, ni JWT ;
  - instances désignées par leur nom ; fichiers par leur chemin (l'« id »
    d'un fichier est son chemin) ;
  - envoi par morceaux du portail (`files/chunk`), pas d'agent de worker ;
  - une seule adresse de base, la publique : le serveur la résout vers
    lui-même, la publication n'a donc rien à traduire ;
  - erreurs du portail : `{"error": …}`, 507 espace plein, 403 licence.
"""
import json
from .i18n import tr, tr_serveur, LANGUE
import os
import ssl
import time
import uuid
import datetime
import http.client
from urllib.parse import urlparse, urlencode, quote

from . import journal
from .api_client import LizpackSession


# Un morceau d'envoi : sous la limite de 64 Mio par requête du portail, et
# assez court pour qu'un proxy ne coupe pas la requête en route.
MORCEAU = 16 * 1024 * 1024

# États du portail → états compris par l'interface du plugin.
_ETATS = {
    'running': 'RUNNING', 'stopped': 'STOPPED', 'creating': 'DEPLOYING',
    'failed': 'ERROR',
}

# Gravités du portail → celles du rapport de validation du plugin.
_GRAVITES = {'bloquant': 'bloquant', 'critique': 'important', 'lent': 'remarque'}


def normaliser_adresse(adresse):
    """« portail.exemple.org » → « https://portail.exemple.org »."""
    adresse = (adresse or '').strip().rstrip('/')
    if adresse and '://' not in adresse:
        adresse = 'https://' + adresse
    return adresse


MSG_PROTEGES = (tr("Les projets QGIS de cette instance sont protégés : leur "
                "téléchargement et leur ouverture sont désactivés (portail, fiche "
                "de l'instance > Paramètres). Les données restent accessibles."))

class SessionEntreprise(LizpackSession):
    """Session ouverte sur le portail d'un serveur LizPack Entreprise."""

    entreprise = True

    def __init__(self, adresse, certificat=''):
        super().__init__()
        self._adresse = normaliser_adresse(adresse)
        # Certificat d'autorité d'un portail interne (fichier .pem/.crt),
        # quand le certificat du portail n'est pas reconnu par le système.
        self._certificat = (certificat or '').strip()
        self._db = {}

    @property
    def api_base(self):
        return self._adresse

    def _get_conn(self):
        if self._conn is not None:
            return self._conn
        p = urlparse(self.api_base)
        if p.scheme == 'http':
            self._conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=300)
        else:
            ctx = ssl.create_default_context()
            if self._certificat:
                ctx.load_verify_locations(self._certificat)
            self._conn = http.client.HTTPSConnection(
                p.hostname, p.port or 443, timeout=300, context=ctx)
        return self._conn

    def _base_headers(self):
        return {
            'User-Agent': 'LizpackPublisher (QGIS plugin)',
            'Authorization': f'Bearer {self._jeton}',
            'Connection': 'keep-alive',
            'Accept-Language': LANGUE,
        }

    def _base_headers_avec_equipe(self):
        return self._base_headers()

    def _chemin(self, suite):
        return f'/api/instances/{quote(str(self._instance_id), safe="")}/{suite}'

    # ── Connexion ────────────────────────────────────────────────────

    def authenticate(self, _identifiant, jeton):
        """Le « mot de passe » est le jeton d'API du portail."""
        if not self._adresse:
            raise Exception(tr("Indiquez l'adresse du portail de votre organisation."))
        jeton = (jeton or '').strip()
        if not jeton:
            raise Exception(tr("Indiquez votre jeton d'API."))
        self._jeton = jeton
        try:
            self.moi = self._api('GET', '/api/me') or {}
            self.ecriture = not self.moi.get('jeton_lecture_seule')
        except Exception:
            self._jeton = ''
            raise
        try:
            # Contact de support de l'organisation (route publique).
            self.branding = self._api('GET', '/api/branding') or {}
        except Exception as e:
            journal.ignorer(e, "lecture de l'apparence du portail")
            self.branding = {}
        return self._get_instances()

    def get_memberships(self):
        self.memberships = []
        return []

    def set_team_context(self, owner_id):
        self._team_owner_id = None

    def _get_instances(self):
        liste = self._api('GET', '/api/instances') or []
        out = []
        for i in liste:
            perms = i.get('perms') or []
            out.append({
                'id': i.get('name'), 'name': i.get('name'),
                'status': _ETATS.get(i.get('status', ''), (i.get('status') or '').upper()),
                'domain': i.get('domain', ''),
                'perms': perms,
            })
        return out

    def connect_instance(self, instance_id, instance_name):
        self._instance_id = instance_id
        self._instance_name = instance_name
        self.list_files('/')
        self.metadata_error = ''
        self._instance_data = {}
        try:
            d = self._api('GET', self._chemin('').rstrip('/')) or {}
            perms = d.get('perms') or []
            self.projets_proteges = bool(d.get('proteger_projets'))
            self.permissions = {
                'can_manage_files': 'instances.files' in perms,
                'can_manage_projects': 'instances.projects' in perms,
            }
            mot_de_passe = ''
            try:
                bases = self._api('GET', self._chemin('databases')) or []
                for b in bases:
                    if b.get('name') == d.get('db_name'):
                        mot_de_passe = b.get('password', '')
            except Exception as e:
                journal.ignorer(e, 'lecture des bases de l\'instance')
            self._instance_data = {
                'db_host': d.get('db_host', ''), 'db_port': d.get('db_port') or 5432,
                'db_name': d.get('db_name', ''), 'db_user': d.get('db_user', ''),
                'db_password': mot_de_passe,
            }
            if not d.get('db_host'):
                self.metadata_error = (
                    tr("l'adresse publique de la base n'est pas renseignée dans le portail "
                    '(instance > Bases de données)'))
            elif not mot_de_passe:
                self.metadata_error = (
                    tr("votre rôle ne donne pas accès au mot de passe de la base "
                    '(droit « voir les identifiants des bases »)'))
        except Exception as e:
            self.metadata_error = str(e)

    def get_postgis_internal(self):
        # Le serveur résout l'adresse publique vers lui-même.
        return self.get_postgis_uri()

    # ── Fichiers ─────────────────────────────────────────────────────

    def list_files(self, api_path='/'):
        rep = self._api('GET', self._chemin('files'), params={'path': api_path.strip('/')}) or {}
        base = '/' + api_path.strip('/')
        out = []
        if not hasattr(self, '_miens'):
            self._miens = set()
        for e in rep.get('entrees') or []:
            if e.get('a_moi'):
                self._miens.add((base.rstrip('/') + '/' + e['nom']).lstrip('/'))
            ts = 0.0
            if e.get('modifie_le'):
                try:
                    ts = datetime.datetime.fromisoformat(
                        e['modifie_le'].replace('Z', '+00:00')).timestamp()
                except ValueError as err:
                    journal.ignorer(err, f'date illisible sur {e.get("nom")}')
            chemin = base.rstrip('/') + '/' + e['nom']
            out.append({
                'id': chemin, 'name': e['nom'], 'size': e.get('taille') or 0,
                'modified': ts, 'api_path': chemin, 'is_dir': bool(e.get('dossier')),
                'enfants': e.get('elements') if e.get('dossier') else None,
            })
        return out

    def est_protege(self, chemin):
        """Projet fermé à ce compte (protégé, et ni à lui ni ouvert par
        un groupe de mise à jour : le portail en a déjà tenu compte)."""
        return (getattr(self, 'projets_proteges', False)
                and str(chemin).lower().endswith(('.qgs', '.qgz'))
                and str(chemin).strip('/') not in getattr(self, '_miens', set()))

    def _refuser_protege(self, chemins):
        if any(self.est_protege(c) for c in chemins):
            raise Exception(MSG_PROTEGES)

    def download(self, file_id):
        self._refuser_protege([file_id])
        return self._request('GET', self._chemin('files/download') + '?' + urlencode(
            {'path': str(file_id).strip('/')}), extra_headers={'Accept': '*/*'}, raw=True)

    def download_folder_zip(self, ids, zip_name='projet.zip'):
        self._refuser_protege(ids)
        parents = {os.path.dirname('/' + str(i).strip('/')) for i in ids}
        if len(parents) != 1:
            raise Exception(tr('sélection répartie sur plusieurs dossiers'))
        params = [('path', parents.pop().strip('/'))]
        params += [('n', os.path.basename(str(i).rstrip('/'))) for i in ids]
        if len(ids) == 1:
            # Un seul nom : le portail le prendrait pour le nom de l'archive.
            params = [('path', str(ids[0]).strip('/'))]
        return self._request('GET', self._chemin('files/zip') + '?' + urlencode(params),
                             extra_headers={'Accept': '*/*'}, raw=True)

    def _envoyer_entrees(self, entrees, parent_path, progress_cb=None):
        """Chaque fichier par morceaux ; les sous-dossiers sont créés par le
        portail. Les projets partent après leurs données, comme sur le
        mutualisé : une carte n'est jamais publiée avant ses couches."""
        from .envoi_worker import est_projet
        ordre = [e for e in entrees if not est_projet(e[1])] + [e for e in entrees if est_projet(e[1])]
        total = len(ordre)
        for n, (local, rel) in enumerate(ordre):
            if progress_cb:
                progress_cb(n, total, f'{os.path.basename(rel)} ({self._human_size(os.path.getsize(local))})…')
            self._envoyer_fichier(local, rel.replace('\\', '/'), parent_path)
        if progress_cb:
            progress_cb(total, total, tr('{0} / {1} fichier(s) envoyé(s)', total, total))
        return total

    def _envoyer_fichier(self, local, rel, dossier):
        """Un fichier, morceau par morceau. Après une coupure, le portail dit
        ce qu'il a déjà reçu et l'envoi reprend de là."""
        base = {'path': dossier.strip('/'), 'rel': rel, 'id': uuid.uuid4().hex}
        taille = os.path.getsize(local)
        offset, echecs = 0, 0
        with open(local, 'rb') as f:
            while True:
                f.seek(offset)
                morceau = f.read(MORCEAU)
                fin = offset + len(morceau) >= taille
                q = dict(base, offset=offset, **({'fin': '1'} if fin else {}))
                try:
                    self._request('POST', self._chemin('files/chunk') + '?' + urlencode(q),
                                  body=morceau, extra_headers={
                                      'Content-Type': 'application/octet-stream',
                                      'Accept': 'application/json'})
                except Exception as e:
                    texte = str(e)
                    # Droits, quota, licence : insister n'y changerait rien.
                    definitif = texte.startswith(('API 4', tr("Espace de l'instance plein : {0}", ''))) and not texte.startswith('API 409')
                    echecs += 1
                    if definitif or echecs > 4:
                        raise
                    time.sleep(2 ** min(echecs, 3))
                    try:
                        etat = self._api('GET', self._chemin('files/chunk/etat'), params=base) or {}
                        offset = int(etat.get('recu') or 0)
                    except Exception as err:
                        journal.ignorer(err, "état d'un envoi interrompu")
                    continue
                offset += len(morceau)
                echecs = 0
                if fin:
                    return

    def upload_folder(self, local_folder, api_dest, progress_cb=None):
        nom = os.path.basename(local_folder)
        try:
            self.create_folder(nom, api_dest)
        except Exception as e:
            journal.ignorer(e, f'dossier {nom} (existe peut-être déjà)')
        entrees = []
        for racine, dossiers, fichiers in os.walk(local_folder):
            dossiers[:] = sorted(d for d in dossiers if not d.startswith('.'))
            for f in fichiers:
                if f.startswith('.'):
                    continue
                local = os.path.join(racine, f)
                entrees.append((local, nom + '/' + os.path.relpath(local, local_folder).replace('\\', '/')))
        if not entrees:
            return 0
        return self._envoyer_entrees(entrees, api_dest, progress_cb)

    def _corps(self, **champs):
        return json.dumps(champs).encode()

    def delete_file(self, file_id):
        self._api('POST', self._chemin('files/delete'), data=self._corps(path=str(file_id).strip('/')))

    def create_folder(self, name, parent_path='/'):
        return self._api('POST', self._chemin('files/mkdir'),
                         data=self._corps(path=parent_path.strip('/'), nom=name))

    def rename_file(self, file_id, new_name):
        return self._api('POST', self._chemin('files/rename'),
                         data=self._corps(path=str(file_id).strip('/'), nom=new_name))

    def copy_files(self, file_ids, destination_path):
        return self._api('POST', self._chemin('files/copy'), data=self._corps(
            paths=[str(i).strip('/') for i in file_ids], destination=destination_path.strip('/')))

    def move_files(self, file_ids, destination_path):
        return self._api('POST', self._chemin('files/move'), data=self._corps(
            paths=[str(i).strip('/') for i in file_ids], destination=destination_path.strip('/')))

    # ── Validation, diagnostic ───────────────────────────────────────

    def valider_projet(self, local_path=None, file_id=None):
        if not local_path:
            a = self._api('GET', self._chemin('projects/validate'),
                          params={'path': str(file_id).strip('/')})
        else:
            nom = os.path.basename(local_path)
            with open(local_path, 'rb') as f:
                a = self._api_multipart(self._chemin('projects/validate'),
                                        fields={}, files={'file': (nom, f.read())})
        return self._rapport(a or {})

    @staticmethod
    def _rapport(a):
        """Analyse du portail → rapport attendu par le panneau de validation."""
        signalements, resume = [], {'bloquant': 0, 'important': 0, 'remarque': 0}
        if a.get('illisible'):
            a.setdefault('alertes', []).insert(0, {
                'gravite': 'bloquant', 'categorie': 'Projet', 'titre': a['illisible']})
        for al in a.get('alertes') or []:
            g = _GRAVITES.get(al.get('gravite'), 'remarque')
            resume[g] += 1
            signalements.append({
                'severite': g, 'categorie': al.get('categorie', ''),
                'couche': al.get('couche', ''), 'constat': al.get('titre', ''),
                'consequence': al.get('consequence', ''), 'solution': al.get('conseil', ''),
            })
        return {'resume': resume, 'signalements': signalements, 'connexions_conformes': True,
                'erreurs_connexion': []}

    def diagnostiquer_base(self, tables=None):
        raise Exception(
            tr('Sur un serveur de votre organisation, la base est optimisée par le '
            'portail lui-même : instance > Maintenance > Accélérer.'))

    # ── Erreurs ──────────────────────────────────────────────────────

    def _request(self, method, path, body=None, extra_headers=None, raw=False):
        try:
            return super()._request(method, path, body=body, extra_headers=extra_headers, raw=raw)
        except Exception as e:
            raise Exception(self._message(str(e))) from None

    @staticmethod
    def _message(texte):
        """Les erreurs du portail en clair."""
        if texte.startswith('API 401'):
            return tr("API 401 : jeton refusé par le portail (expiré, révoqué ou mal copié).")
        if texte.startswith('API 507'):
            return tr("Espace de l'instance plein : {0}", texte.partition(':')[2].strip())
        return texte
