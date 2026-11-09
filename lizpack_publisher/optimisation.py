# -*- coding: utf-8 -*-
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
optimisation.py
───────────────
Diagnostic et optimisation de la base PostGIS d'une instance.

Deux principes tiennent tout le module :

1. Le diagnostic ne modifie RIEN. Il se contente d'interroger les
   catalogues de PostgreSQL, ce qui reste peu couteux meme sur une base
   volumineuse.

2. Seules les corrections sures sont automatisees. Creer un index,
   rafraichir des statistiques ou recuperer de l'espace mort sont des
   operations reversibles qui ne changent ni le schema ni les donnees.
   Ajouter une clef primaire ou decouper des geometries change le modele :
   ces cas sont signales avec le SQL a executer, jamais appliques.
"""

from . import journal
from .i18n import tr

# Gravites, de la plus forte a la plus faible
GRAVE, MOYEN, MINEUR = 'grave', 'moyen', 'mineur'


def citer(nom):
    """Cite un identifiant SQL comme le ferait PostgreSQL lui-meme.

    Les noms viennent du catalogue, mais rien n'empeche un utilisateur de
    creer une table dont le nom contient un guillemet : colle tel quel, il
    romprait la citation et la suite du nom deviendrait du SQL. Doubler les
    guillemets internes est la regle de PostgreSQL, et elle suffit.
    """
    return '"' + str(nom).replace('"', '""') + '"'




class Probleme:
    """Un defaut constate sur une table, et ce qu'on peut en faire."""

    def __init__(self, table, schema, titre, detail, gravite,
                 sql=None, automatique=False, confirmable=False,
                 consequence='', annulation=''):
        self.table       = table
        self.schema      = schema
        self.titre       = titre
        self.detail      = detail
        self.gravite     = gravite
        self.sql         = sql            # correction, ou None
        self.automatique = automatique    # applicable sans risque
        # Applicable, mais avec une consequence que l'utilisateur doit
        # connaitre avant : verrou sur la table, colonne ajoutee...
        self.confirmable = confirmable
        self.consequence = consequence
        # De quoi revenir en arriere. Un index ou une contrainte se
        # defont ; une colonne ajoutee se supprime. Le dire vaut mieux que
        # de laisser l'utilisateur chercher le nom qu'a choisi PostgreSQL.
        self.annulation  = annulation

    @property
    def cible(self):
        return f'{self.schema}.{self.table}'

    @property
    def applicable(self):
        """Le plugin sait-il executer cette correction ?"""
        return self.automatique or self.confirmable


# ══════════════════════════════════════════════════════════════════════
# Le diagnostic vient du serveur
# ══════════════════════════════════════════════════════════════════════
#
# Les controles ci-dessous ont ete deplaces dans LizPack
# (`backend/application/file_manager/diagnostic_pg.py`) et sont desormais
# demandes par l'API. Deux implementations du meme controle finissaient par
# diverger, et le plugin ne pourrait de toute facon pas diagnostiquer sans le
# serveur : c'est de lui qu'il tient les identifiants de la base.
#
# Ce qui reste ici est ce que le serveur ne fait pas : APPLIQUER les
# corrections, en se connectant en direct, et produire les exports.

# Le serveur classe en bloquant / important / remarque ; le plugin en grave /
# moyen / mineur. Une seule table de correspondance, ici.
GRAVITES_SERVEUR = {
    'bloquant': GRAVE,
    'important': MOYEN,
    'remarque': MINEUR,
}


def depuis_signalement(donnees):
    """Reconstruit un `Probleme` a partir d'un signalement du serveur."""
    cible = donnees.get('cible') or ''
    schema, _, table = cible.partition('.')
    detail = ' '.join(filter(None, (
        donnees.get('constat', ''), donnees.get('consequence', ''),
    )))
    return Probleme(
        table or cible, schema or 'public',
        donnees.get('titre') or donnees.get('constat', '')[:60],
        detail,
        GRAVITES_SERVEUR.get(donnees.get('severite'), MOYEN),
        sql=donnees.get('sql'),
        automatique=bool(donnees.get('automatique')),
        # Une correction que le serveur ne declare pas sure reste applicable,
        # mais seulement apres accord explicite de l'utilisateur.
        confirmable=bool(donnees.get('sql')) and not donnees.get('automatique'),
        consequence=donnees.get('solution', ''),
        annulation=donnees.get('annulation', ''),
    )


def diagnostiquer_par_api(session, avancement=None):
    """Demande le diagnostic au serveur et rend des `Probleme`."""
    if avancement:
        avancement(tr('Diagnostic demandé au serveur LizPack…'))
    signalements = session.diagnostiquer_base()
    return [depuis_signalement(d) for d in signalements]


def _niveau(probleme):
    """Comment la correction sera appliquee, en clair."""
    if probleme.automatique:
        return tr('Automatique')
    if probleme.confirmable:
        return tr('Sur confirmation')
    return tr('À la main')


def exporter_csv(problemes, instance, base):
    """Rapport tabulaire, destine a etre lu ou transmis.

    Encode en UTF-8 avec marque d'ordre : sans elle, Excel affiche les
    accents de travers, et c'est le premier logiciel ou ce fichier
    finira.
    """
    import csv
    import io as _io

    tampon = _io.StringIO()
    graveur = csv.writer(tampon, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    graveur.writerow([tr('Instance'), instance, tr('Base'), base])
    graveur.writerow([
        tr('Gravité'), tr('Schéma'), tr('Table'), tr('Problème'), tr('Correction'),
        tr('Détail'), 'SQL', tr('Conséquence'), tr('Annulation'),
    ])
    for p in problemes:
        graveur.writerow([
            p.gravite, p.schema, p.table, p.titre, _niveau(p),
            p.detail, (p.sql or '').strip(), p.consequence, p.annulation,
        ])
    return '\ufeff' + tampon.getvalue()


def exporter_sql(problemes, instance, base):
    """Script rejouable, corrections commentees et regroupees par nature.

    Les corrections manuelles y figurent aussi, mais commentees : le
    script ne doit rien appliquer que l'utilisateur n'ait relu.
    """
    import datetime

    lignes = [
        '-- ' + tr('Diagnostic de la base LizPack'),
        '-- ' + tr('Instance : {0}', instance),
        '-- ' + tr('Base : {0}', base),
        '-- ' + tr('Généré le : {0}', f'{datetime.datetime.now():%Y-%m-%d %H:%M}'),
        '-- ' + tr('{0} point(s) relevé(s)', len(problemes)),
        '--',
        '-- ' + tr('Les corrections « à la main » sont commentées : relisez-les avant de les activer.'),
        '',
    ]
    ordre = [
        (tr('Corrections sans risque'), lambda p: p.automatique),
        (tr('Corrections à confirmer'), lambda p: p.confirmable),
        (tr('À traiter à la main'), lambda p: not p.applicable),
    ]
    for titre, garde in ordre:
        lot = [p for p in problemes if garde(p)]
        if not lot:
            continue
        lignes += ['-- ' + '=' * 68, f'-- {titre} ({len(lot)})',
                   '-- ' + '=' * 68, '']
        for p in lot:
            lignes.append(f'-- {p.cible} : {p.titre}')
            lignes.append(f'--    {p.detail}')
            if p.consequence:
                lignes.append('--    ' + tr('Conséquence : {0}', p.consequence))
            corps = (p.sql or '').strip()
            if not corps:
                lignes.append('')
                continue
            if not p.applicable:
                corps = '\n'.join(
                    x if x.lstrip().startswith('--') else '-- ' + x
                    for x in corps.split('\n')
                )
            elif not corps.rstrip().endswith(';'):
                corps += ';'
            lignes.append(corps)
            if p.annulation:
                lignes.append('--    ' + tr('Pour défaire : {0};', p.annulation))
            lignes.append('')
    return '\n'.join(lignes)


def appliquer(connexion, problemes, avancement=None):
    """Applique les corrections marquees comme sures.

    Chaque instruction est jouee isolement : une table verrouillee ou
    disparue ne doit pas faire echouer les autres. Retourne
    (reussies, echouees).
    """
    def dire(message):
        if avancement:
            avancement(message)

    reussies, echouees = [], []
    # VACUUM refuse de s'executer dans une transaction.
    ancien_autocommit = connexion.autocommit
    connexion.autocommit = True
    try:
        for probleme in problemes:
            if not probleme.applicable or not probleme.sql:
                continue
            dire(f'{probleme.cible} — {probleme.titre.lower()}…')
            curseur = connexion.cursor()
            try:
                curseur.execute(probleme.sql)
                reussies.append(probleme)
            except Exception as e:
                echouees.append((probleme, str(e).strip().splitlines()[0]))
            finally:
                try:
                    curseur.close()
                except Exception as e:
                    journal.ignorer(e, 'fermeture du curseur')
    finally:
        connexion.autocommit = ancien_autocommit
    return reussies, echouees
