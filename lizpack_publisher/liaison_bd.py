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
liaison_bd.py
─────────────
Rebranche les couches PostGIS d'un projet telecharge sur la base de
l'instance.

Un projet publie porte l'adresse *interne* de la base — celle que Lizmap
emploie depuis le serveur — et, selon son histoire, un mot de passe
perime ou aucun. Ouvert sur un poste de travail, il ne joint donc rien :
QGIS ouvre la boite « Traiter les couches inutilisables » et le projet
arrive vide.

On reecrit l'adresse vers celle que l'API donne au poste de travail, et
on remplace les identifiants par une reference au magasin
d'authentification de QGIS. Deux consequences voulues :

  - le mot de passe de la base ne s'ecrit jamais en clair sur le disque ;
  - la publication, qui retire `authcfg` et repose les identifiants
    internes, continue de fonctionner sans changement.

Seules sont touchees les couches qui pointent vers la base de
l'instance : un projet melangeant plusieurs serveurs garde les siennes.
"""

import io
import os
import re
import shutil
import tempfile
import zipfile

MOTIF_SOURCE = re.compile(r'(<datasource>)(.*?)(</datasource>)', re.DOTALL)


def _dbname(source):
    trouve = re.search(r"dbname='([^']*)'", source)
    return trouve.group(1) if trouve else None


def _echapper(valeur):
    """Echappe une valeur pour une chaine de connexion PostgreSQL."""
    return (valeur or '').replace(chr(92), chr(92) * 2).replace("'", chr(92) + "'")


def _reecrire_source(source, pg, authcfg):
    """Repose l'adresse et les identifiants d'une seule source PostGIS."""
    source = re.sub(r"host=[^\s'\"]+", "host={}".format(pg['host']), source)
    if re.search(r'port=\d+', source):
        source = re.sub(r'port=\d+', 'port={}'.format(pg['port']), source)
    else:
        source = re.sub(r"(dbname='[^']*')",
                        r"\1 port={}".format(pg['port']), source, count=1)

    # Ce qui restait des identifiants precedents s'en va, quel qu'il soit.
    source = re.sub(r"\s*authcfg=\S+", '', source)
    source = re.sub(r"\s*password='[^']*'", '', source)
    source = re.sub(r"\s*user='[^']*'", '', source)

    if authcfg:
        identite = 'authcfg={}'.format(authcfg)
    else:
        # Repli : le magasin d'authentification est indisponible. Mieux
        # vaut un projet qui s'ouvre qu'un projet vide ; l'appelant
        # previent l'utilisateur que le mot de passe est ecrit en clair.
        identite = "user='{}' password='{}'".format(
            _echapper(pg['user']), _echapper(pg['password']))

    # Insertion par decoupage plutot que par re.sub : le mot de passe peut
    # contenir une barre oblique inversee, qu'un gabarit de remplacement
    # interpreterait.
    place = re.search(r"dbname='[^']*'", source)
    if place is None:
        return source
    return source[:place.end()] + ' ' + identite + source[place.end():]


def reecrire_texte(contenu, pg, authcfg=None):
    """Retourne (contenu reecrit, nombre de couches rebranchees)."""
    compte = [0]

    def remplacer(m):
        source = m.group(2)
        if 'dbname=' not in source or _dbname(source) != pg['dbname']:
            return m.group(0)
        compte[0] += 1
        return m.group(1) + _reecrire_source(source, pg, authcfg) + m.group(3)

    return MOTIF_SOURCE.sub(remplacer, contenu), compte[0]


def relier(chemin, pg, authcfg=None):
    """Rebranche le projet designe. Retourne le nombre de couches touchees.

    Accepte un `.qgs` comme un `.qgz` — ce dernier est une archive dont on
    ne reecrit que le projet, les autres membres etant recopies tels
    quels.
    """
    if not pg or not pg.get('host') or not pg.get('dbname'):
        return 0

    if chemin.lower().endswith('.qgz'):
        return _relier_archive(chemin, pg, authcfg)

    with io.open(chemin, encoding='utf-8', errors='ignore') as f:
        contenu = f.read()
    contenu, compte = reecrire_texte(contenu, pg, authcfg)
    if compte:
        with io.open(chemin, 'w', encoding='utf-8') as f:
            f.write(contenu)
    return compte


def _relier_archive(chemin, pg, authcfg):
    compte = 0
    dossier = tempfile.mkdtemp(prefix='lizpack_qgz_')
    provisoire = os.path.join(dossier, 'projet.qgz')
    try:
        with zipfile.ZipFile(chemin) as source:
            membres = source.infolist()
            with zipfile.ZipFile(provisoire, 'w', zipfile.ZIP_DEFLATED) as cible:
                for membre in membres:
                    donnees = source.read(membre.filename)
                    if membre.filename.lower().endswith('.qgs'):
                        texte, compte = reecrire_texte(
                            donnees.decode('utf-8', 'ignore'), pg, authcfg)
                        donnees = texte.encode('utf-8')
                    cible.writestr(membre, donnees)
        if compte:
            shutil.copyfile(provisoire, chemin)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    return compte
