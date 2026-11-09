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
envoi_worker.py
───────────────
Envoi des données directement au serveur qui héberge l'instance.

Avant, une publication partait en une seule requête vers le central : tout
le projet et ses données chargés en mémoire, rien de compressé, tout renvoyé
à chaque fois, et une requête de plus d'une minute et demie environ coupée
en route (au-delà de 25 Mo sur une ligne à 2 Mbit/s). L'envoi suit
maintenant la même méthode que l'espace client :

- les fichiers déjà à jour sur le serveur ne repartent pas ;
- un fichier modifié n'envoie que ses blocs de 4 Mio qui ont changé (un
  GeoPackage modifie ses pages sur place : corriger quelques entités d'un
  fichier de 300 Mo n'envoie que quelques Mo) ;
- chaque bloc est compressé quand le format s'y prête (GeoPackage,
  Shapefile, CSV : 2 à 3 fois moins d'octets) ;
- un bloc perdu se réessaie, et un envoi interrompu (coupure, QGIS fermé)
  reprend là où il s'était arrêté ;
- chaque bloc est vérifié à l'arrivée par son empreinte.

Les projets QGIS, eux, passent toujours par le central, qui les valide.
"""
import gzip
from .i18n import tr, tr_serveur
import hashlib
import http.client
import json
import os
import ssl
import time
import uuid
from urllib.parse import urlparse, urlencode

from . import journal

BLOC = 4 * 1024 * 1024
LOT_MAX = 4 * 1024 * 1024
DEJA_COMPRESSES = {
    'zip', 'qgz', 'gz', 'tgz', '7z', 'rar', 'bz2', 'xz', 'zst',
    'jpg', 'jpeg', 'png', 'webp', 'gif', 'jp2', 'ecw', 'sid',
    'mp4', 'mov', 'avi', 'mkv', 'mp3', 'pdf', 'docx', 'xlsx', 'pptx', 'odt', 'ods',
}


def est_projet(nom):
    n = nom.lower()
    return n.endswith('.qgs') or n.endswith('.qgz') or n.endswith('.qgs.cfg')


def compressible(nom):
    return nom.rsplit('.', 1)[-1].lower() not in DEJA_COMPRESSES


def taille_lisible(n):
    for unite in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024 or unite == 'Go':
            return f'{n:.0f} {unite}' if unite == 'o' else f'{n:.1f} {unite}'.replace('.', ',')
        n /= 1024


class RefusAgent(Exception):
    """Refus explicite de l'agent (4xx) : inutile de réessayer."""

    def __init__(self, message, statut):
        super().__init__(message)
        self.statut = statut


class EnvoiWorker:
    """Client de l'agent de fichiers du worker, pour une instance."""

    def __init__(self, session):
        self.session = session
        self._acces = None
        self._conn = None
        self.mesure = {
            'mode': 'worker', 'client': 'qgis', 'fichiers': 0, 'ignores': 0, 'echecs': 0,
            'octets_fichiers': 0, 'octets_envoyes': 0, 'nouvelles_tentatives': 0,
            'reprises': 0, 'blocs_evites': 0,
        }
        self._debut = time.monotonic()

    # ── accès ────────────────────────────────────────────────────────

    @classmethod
    def ouvrir(cls, session):
        """L'envoi par le worker, ou None si l'instance passe par le central."""
        envoi = cls(session)
        try:
            return envoi if envoi._jeton() else None
        except Exception as e:
            journal.ignorer(e, "accès à l'agent du worker")
            return None

    def _jeton(self):
        a = self._acces
        if a is None or a['expire'] - time.time() < 90:
            rep = self.session._api('GET', f'/api/instances/{self.session.instance_id}/files/acces/')
            if not rep or rep.get('mode') != 'worker' or not rep.get('ecrire'):
                return None
            if self._acces is None or urlparse(rep['url']).hostname != urlparse(self._acces['url']).hostname:
                self._fermer()
            self._acces = {'url': rep['url'].rstrip('/'), 'jeton': rep['jeton'], 'expire': rep['expire']}
        return self._acces['jeton']

    def _fermer(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception as e:
                journal.ignorer(e, "fermeture de la connexion à l'agent")
        self._conn = None

    # ── transport ────────────────────────────────────────────────────

    def _requete(self, methode, route, corps=None, entetes=None, params=None):
        """Une requête à l'agent ; rend (statut, données JSON)."""
        jeton = self._jeton()
        u = urlparse(self._acces['url'])
        chemin = u.path + route + ('?' + urlencode(params) if params else '')
        h = {'Authorization': f'Bearer {jeton}', 'Connection': 'keep-alive',
             'User-Agent': 'LizpackPublisher (QGIS)'}
        h.update(entetes or {})
        for essai in range(2):
            if self._conn is None:
                if u.scheme == 'http':  # essais sur un agent local
                    self._conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=120)
                else:
                    self._conn = http.client.HTTPSConnection(
                        u.hostname, u.port or 443, timeout=120, context=ssl.create_default_context())
            try:
                self._conn.request(methode, chemin, body=corps, headers=h)
                rep = self._conn.getresponse()
                brut = rep.read()
            except (OSError, http.client.HTTPException):
                self._fermer()
                if essai == 0:
                    continue
                raise
            try:
                donnees = json.loads(brut.decode()) if brut.strip() else {}
            except ValueError:
                donnees = {}
            return rep.status, donnees
        return 0, {}

    def _json(self, route, corps):
        return self._requete('POST', route, json.dumps(corps).encode(), {'Content-Type': 'application/json'})

    def _avec_reprises(self, faire, quoi):
        """Réessaie une opération après une coupure, avec un délai croissant."""
        for essai in range(7):
            try:
                statut, donnees = faire()
            except (OSError, http.client.HTTPException) as e:
                if essai == 6:
                    raise Exception(tr('{0} : connexion interrompue ({1})', quoi, e))
            else:
                if 200 <= statut < 300:
                    return donnees
                if 400 <= statut < 500 and statut not in (408, 429):
                    raise RefusAgent(tr_serveur(donnees.get('error')) or tr('{0} : refus {1}', quoi, statut), statut)
                if essai == 6:
                    raise Exception(tr('{0} : erreur {1}', quoi, statut))
            self.mesure['nouvelles_tentatives'] += 1
            time.sleep(min(30, 2 ** essai))

    @staticmethod
    def _multipart(champs, fichiers):
        frontiere = uuid.uuid4().hex
        morceaux = []
        for cle, val in champs:
            morceaux.append(f'--{frontiere}\r\nContent-Disposition: form-data; name="{cle}"\r\n\r\n{val}\r\n'.encode())
        for cle, nom, contenu in fichiers:
            morceaux.append(
                f'--{frontiere}\r\nContent-Disposition: form-data; name="{cle}"; filename="{nom}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n'.encode())
            morceaux.append(contenu)
            morceaux.append(b'\r\n')
        morceaux.append(f'--{frontiere}--\r\n'.encode())
        return b''.join(morceaux), f'multipart/form-data; boundary={frontiere}'

    # ── opérations ───────────────────────────────────────────────────

    def deja_a_jour(self, parent, entrees):
        """Les entrées (local, rel) déjà présentes à l'identique sur le serveur
        (même taille, copie du serveur plus récente)."""
        if not entrees:
            return set()
        try:
            statut, d = self._json('/existants', {'parent_path': parent, 'chemins': [r for _l, r in entrees]})
        except Exception as e:
            journal.ignorer(e, 'fichiers déjà présents')
            return set()
        if statut != 200:
            return set()
        existants = d.get('fichiers') or {}
        out = set()
        for local, rel in entrees:
            e = existants.get(rel)
            if e and e.get('size') == os.path.getsize(local) and os.path.getmtime(local) * 1000 <= e.get('mtime', 0):
                out.add((local, rel))
        return out

    def envoyer_lot(self, parent, entrees):
        """Petits fichiers, en une requête (moins de 4 Mo en tout)."""
        champs = [('parent_path', parent)]
        fichiers = []
        for local, rel in entrees:
            with open(local, 'rb') as f:
                fichiers.append(('files', os.path.basename(rel), f.read()))
            champs.append(('paths', rel))
        corps, type_ = self._multipart(champs, fichiers)
        self.mesure['octets_envoyes'] += len(corps)
        d = self._avec_reprises(lambda: self._requete('POST', '/envoi', corps, {'Content-Type': type_}), 'envoi')
        bloques = d.get('blocked_files') or []
        if bloques:
            raise Exception('\n'.join(f"{b.get('name')} : {b.get('reason')}" for b in bloques))

    def _empreintes_locales(self, local):
        out = []
        with open(local, 'rb') as f:
            while True:
                bloc = f.read(BLOC)
                if not bloc:
                    break
                out.append(hashlib.sha256(bloc).hexdigest())
        return out

    def envoyer_fichier(self, local, rel, parent, suivi=None):
        """Un fichier par blocs : reprise, envoi différentiel, compression."""
        taille = os.path.getsize(local)
        nom = os.path.basename(rel)
        chemin = parent.rstrip('/') + '/' + rel
        locales = self._empreintes_locales(local) if taille else []
        n = max(1, len(locales))
        compresser = False
        if compressible(nom) and taille > 256 * 1024:
            with open(local, 'rb') as f:
                essai = f.read(BLOC)
            compresser = len(gzip.compress(essai, 6)) < len(essai) * 0.9

        base = None
        if taille >= 2 * BLOC:
            try:
                statut, d = self._json('/empreintes', {'path': chemin, 'bloc': BLOC})
                if statut == 200 and d.get('empreintes'):
                    base = d
            except Exception as e:
                journal.ignorer(e, 'empreintes du fichier en place')

        def tenter(delta):
            a_envoyer = [i for i in range(n)
                         if not delta or i >= len(base['empreintes']) or base['empreintes'][i] != locales[i]]
            if delta and len(a_envoyer) == n:
                return tenter(False)
            champs = {
                'file_name': nom, 'file_size': taille, 'file_path': rel, 'parent_path': parent,
                'compressed': compresser, 'bloc': BLOC if taille else 0, 'empreintes': locales,
                'cle': f'{chemin}|{taille}|{int(os.path.getmtime(local) * 1000)}',
            }
            if delta:
                champs.update({'delta': True, 'base_taille': base['size'], 'base_mtime': base['mtime']})
            try:
                d = self._avec_reprises(lambda: self._json('/envoi/debut', champs), tr('début de l\'envoi'))
            except RefusAgent as e:
                if delta and e.statut == 409:
                    return tenter(False)
                raise
            identifiant = d['upload_id']
            recus = set(d.get('recus') or [])
            if recus:
                self.mesure['reprises'] += 1
            if delta:
                self.mesure['blocs_evites'] += n - len(a_envoyer)
            restants = [i for i in a_envoyer if i not in recus]
            faits = len(a_envoyer) - len(restants)
            with open(local, 'rb') as f:
                for i in restants:
                    f.seek(i * BLOC)
                    bloc = f.read(BLOC)
                    if compresser:
                        bloc = gzip.compress(bloc, 6)
                    corps, type_ = self._multipart(
                        [('upload_id', identifiant), ('chunk_index', str(i))], [('chunk', f'chunk_{i}', bloc)])
                    self.mesure['octets_envoyes'] += len(bloc)
                    self._avec_reprises(
                        lambda c=corps, t=type_: self._requete('POST', '/envoi/morceau', c, {'Content-Type': t}),
                        f'{nom}, bloc {i + 1}/{n}')
                    faits += 1
                    if suivi:
                        suivi(faits, len(a_envoyer))
            try:
                return self._avec_reprises(
                    lambda: self._json('/envoi/fin', {'upload_id': identifiant}), tr('fin de l\'envoi'))
            except RefusAgent as e:
                if delta and e.statut == 409:
                    return tenter(False)
                raise

        return tenter(bool(base))

    def envoyer(self, parent, entrees, progress_cb=None):
        """Envoie des fichiers (local, rel) hors projets QGIS. Rend le nombre
        de fichiers à jour sur le serveur à la fin (envoyés ou déjà là)."""
        identiques = self.deja_a_jour(parent, entrees)
        self.mesure['fichiers'] += len(entrees)
        self.mesure['ignores'] += len(identiques)
        a_faire = [e for e in entrees if e not in identiques]
        total = len(entrees)
        fait = len(identiques)
        if identiques and progress_cb:
            progress_cb(fait, total, tr('{0} fichier(s) déjà à jour, non renvoyé(s)', len(identiques)))
        lot, octets_lot = [], 0

        def vider_lot():
            nonlocal lot, octets_lot, fait
            if lot:
                self.envoyer_lot(parent, lot)
                fait += len(lot)
                if progress_cb:
                    progress_cb(fait, total, tr('{0} petit(s) fichier(s) envoyé(s)', len(lot)))
            lot, octets_lot = [], 0

        for local, rel in a_faire:
            taille = os.path.getsize(local)
            self.mesure['octets_fichiers'] += taille
            gros = taille > LOT_MAX or (compressible(rel) and taille > 256 * 1024)
            if not gros:
                if octets_lot + taille > LOT_MAX or len(lot) >= 200:
                    vider_lot()
                lot.append((local, rel))
                octets_lot += taille
                continue
            nom = os.path.basename(rel)

            def suivi(f, t, nom=nom, taille=taille):
                if progress_cb:
                    progress_cb(fait, total, f'{nom} ({taille_lisible(taille)}) : {round(f * 100 / max(1, t))} %')

            if progress_cb:
                progress_cb(fait, total, tr('{0} ({1}) : comparaison avec le serveur…', nom, taille_lisible(taille)))
            self.envoyer_fichier(local, rel, parent, suivi)
            fait += 1
        vider_lot()
        return total

    def remettre_mesure(self, echecs=0):
        """Le coût de l'envoi, au central (sans effet si cela échoue)."""
        self.mesure['echecs'] += echecs
        self.mesure['duree_ms'] = int((time.monotonic() - self._debut) * 1000)
        try:
            self.session._api('POST', f'/api/instances/{self.session.instance_id}/files/mesure_envoi/',
                              data=json.dumps(self.mesure).encode())
        except Exception as e:
            journal.ignorer(e, "relevé de l'envoi")
        self._fermer()
