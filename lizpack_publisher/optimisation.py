# -*- coding: utf-8 -*-
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


def cible_sql(schema, table):
    return f'{citer(schema)}.{citer(table)}'


def nom_index(table, colonne, suffixe='gist'):
    """Nom d'index lisible et previsible, tronque a la limite de PostgreSQL.

    Sans nom explicite, PostgreSQL en choisit un et l'utilisateur doit
    aller le chercher pour defaire l'operation.
    """
    base = f'{table}_{colonne}_{suffixe}'.replace(' ', '_')
    return base[:63]


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
# Ce que le diagnostic ne regarde pas
# ══════════════════════════════════════════════════════════════════════

# Schemas de service. « lizmap » abrite les tables de l'application
# elle-meme, qui ne sont pas des donnees cartographiques.
SCHEMAS_EXCLUS = (
    'pg_catalog', 'information_schema', 'topology',
    'tiger', 'tiger_data', 'lizmap',
)

# Tables de service reconnaissables a leur nom : PostGIS (spatial_ref_sys
# et ses vues), QGIS (styles et projets stockes en base), et Lizmap, dont
# les tables se rangent parfois dans le meme schema que les donnees.
TABLES_EXCLUES = (
    'spatial_ref_sys', 'layer_styles', 'qgis_projects',
    'geometry_columns', 'geography_columns',
    'raster_columns', 'raster_overviews',
)

# Prefixes des tables applicatives de Lizmap et de son socle Jelix.
PREFIXES_EXCLUS = '^(lizmap_|jacl2|jlx_|jauth|jcommunity_|jsession|jpref)'


def filtre_sql(schema, table):
    """Condition SQL ecartant les tables de service.

    Une seule definition pour les six controles : sans cela, en ajouter
    un revenait a oublier l'exclusion quelque part.
    """
    schemas = ', '.join(f"'{n}'" for n in SCHEMAS_EXCLUS)
    tables = ', '.join(f"'{n}'" for n in TABLES_EXCLUES)
    return (f'{schema} NOT IN ({schemas})\n'
            f'  AND {table} NOT IN ({tables})\n'
            f"  AND {table} !~ '{PREFIXES_EXCLUS}'")


# ══════════════════════════════════════════════════════════════════════
# Requetes de diagnostic
# ══════════════════════════════════════════════════════════════════════

# Colonnes geometriques depourvues d'index spatial.
# Sans index, chaque affichage de carte lit la table entiere.
SQL_SANS_INDEX = """
SELECT g.f_table_schema, g.f_table_name, g.f_geometry_column,
       COALESCE(c.reltuples::bigint, 0)
FROM geometry_columns g
JOIN pg_class     c ON c.relname = g.f_table_name
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = g.f_table_schema
WHERE {filtre_index}
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i
      JOIN pg_class ic ON ic.oid = i.indexrelid
      JOIN pg_am   am  ON am.oid = ic.relam
      JOIN pg_attribute a
        ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
      WHERE i.indrelid = c.oid
        AND am.amname = 'gist'
        AND a.attname = g.f_geometry_column
  )
ORDER BY c.reltuples DESC
"""

# Tables geometriques sans clef primaire entiere.
# QGIS a besoin d'un identifiant entier unique ; a defaut il lit toute la
# table pour fabriquer ses identifiants d'entite.
SQL_SANS_CLEF = """
SELECT n.nspname, c.relname, c.oid, COALESCE(c.reltuples::bigint, 0),
       EXISTS (SELECT 1 FROM pg_constraint k
               WHERE k.conrelid = c.oid AND k.contype = 'p') AS a_une_clef
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND {filtre_classe}
  AND EXISTS (SELECT 1 FROM geometry_columns g
              WHERE g.f_table_schema = n.nspname AND g.f_table_name = c.relname)
  -- Ni clef primaire entiere...
  AND NOT EXISTS (
      SELECT 1 FROM pg_constraint k
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (k.conkey)
      JOIN pg_type t ON t.oid = a.atttypid
      WHERE k.conrelid = c.oid AND k.contype = 'p'
        AND t.typname IN ('int2','int4','int8')
  )
  -- ... ni simple colonne entiere unique et non nulle, qui suffit
  -- pourtant a QGIS pour identifier ses entites.
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = i.indkey[0]
      JOIN pg_type t ON t.oid = a.atttypid
      WHERE i.indrelid = c.oid AND i.indisunique
        AND i.indnatts = 1 AND a.attnotnull
        AND t.typname IN ('int2','int4','int8')
  )
ORDER BY c.reltuples DESC
"""

# Colonnes entieres qui pourraient servir de clef. Les noms usuels
# d'abord : c'est presque toujours l'une d'elles.
SQL_CANDIDATS = """
SELECT a.attname, a.attnotnull, t.typname
FROM pg_attribute a
JOIN pg_type t ON t.oid = a.atttypid
WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
  AND t.typname IN ('int2','int4','int8')
-- Un int4 d'abord : QGIS Serveur refuse le bigint comme clef primaire, et
-- proposer une colonne int8 reviendrait a creer le defaut suivant.
ORDER BY CASE t.typname WHEN 'int4' THEN 0 WHEN 'int2' THEN 1 ELSE 2 END,
         CASE lower(a.attname)
           WHEN 'fid' THEN 0 WHEN 'id' THEN 1 WHEN 'gid' THEN 2
           WHEN 'objectid' THEN 3 WHEN 'ogc_fid' THEN 4 ELSE 5 END,
         a.attnum
"""

# Au-dela, on renonce a verifier l'unicite : la lecture complete de la
# table couterait plus cher que le diagnostic entier.
SEUIL_VERIFICATION_UNICITE = 2000000

# Statistiques absentes ou perimees : le planificateur choisit alors des
# plans au hasard, et ignore souvent les index disponibles.
SQL_STATISTIQUES = """
SELECT s.schemaname, s.relname,
       COALESCE(c.reltuples::bigint, 0),
       s.n_mod_since_analyze,
       (s.last_analyze IS NULL AND s.last_autoanalyze IS NULL) AS jamais
FROM pg_stat_user_tables s
JOIN pg_class c ON c.oid = s.relid
WHERE {filtre_stat_joint}
  AND (
      (s.last_analyze IS NULL AND s.last_autoanalyze IS NULL AND c.reltuples > 0)
      OR s.n_mod_since_analyze > GREATEST(1000, c.reltuples * 0.1)
  )
ORDER BY s.n_mod_since_analyze DESC
"""

# Lignes mortes accumulees : la table occupe et fait lire plus que son
# contenu reel.
SQL_LIGNES_MORTES = """
SELECT schemaname, relname, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
WHERE {filtre_stat}
  AND n_dead_tup > 1000
  AND n_dead_tup > n_live_tup * 0.2
ORDER BY n_dead_tup DESC
"""

# Geometries tres detaillees. Leur boite englobante couvre tout, si bien
# que l'index spatial ne filtre plus rien.
SQL_GEOMETRIES_LOURDES = """
SELECT f_table_schema, f_table_name, f_geometry_column
FROM geometry_columns
WHERE {filtre_geom}
  AND type ILIKE '%POLYGON%'
"""

SQL_SOMMETS = 'SELECT COALESCE(MAX(ST_NPoints({geom})), 0) FROM {cible}'

# Noms de table commencant ou finissant par une espace. PostgreSQL les
# accepte, mais ils obligent a citer le nom partout et se pretent aux
# confusions : deux tables peuvent alors ne differer que par une espace
# invisible. Les interfaces affichent souvent le nom detoure, ce qui rend
# le defaut indecelable a l'oeil.
SQL_NOMS_ESPACES = """
SELECT n.nspname, c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','v','m')
  AND {filtre_classe}
  AND c.relname <> btrim(c.relname)
ORDER BY c.relname
"""

# Clefs primaires en bigint. QGIS Serveur ne les accepte pas : le plugin
# Lizmap le signale lui-meme (« Primary key should be an integer int4 …
# neither a bigint nor an integer8 »), et les outils de Lizmap Web Client
# — zoom sur une entite, filtrage — cessent de fonctionner sur la couche.
SQL_CLEF_BIGINT = """
SELECT n.nspname, c.relname, a.attname, c.oid,
       COALESCE(c.reltuples::bigint, 0),
       EXISTS (SELECT 1 FROM pg_constraint f
               WHERE f.confrelid = c.oid AND f.contype = 'f') AS referencee
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_constraint k ON k.conrelid = c.oid AND k.contype = 'p'
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (k.conkey)
JOIN pg_type t ON t.oid = a.atttypid
WHERE c.relkind = 'r'
  AND t.typname = 'int8'
  AND {filtre_classe}
  AND EXISTS (SELECT 1 FROM geometry_columns g
              WHERE g.f_table_schema = n.nspname AND g.f_table_name = c.relname)
ORDER BY c.relname
"""

# Au-dela, la valeur ne tient plus dans un entier 32 bits.
MAX_INT4 = 2147483647

SEUIL_SOMMETS = 10000

# Les requetes ci-dessus portent des gabarits {filtre_*} : on les remplit
# une fois, ici, plutot que dans chaque appel.
_FILTRES = {
    'filtre_index':  filtre_sql('g.f_table_schema', 'g.f_table_name'),
    'filtre_classe': filtre_sql('n.nspname', 'c.relname'),
    'filtre_stat':       filtre_sql('schemaname', 'relname'),
    # La requete des statistiques joint pg_class : relname y existe des
    # deux cotes et doit etre qualifie.
    'filtre_stat_joint': filtre_sql('s.schemaname', 's.relname'),
    'filtre_geom':   filtre_sql('f_table_schema', 'f_table_name'),
}
SQL_SANS_INDEX     = SQL_SANS_INDEX.format(**_FILTRES)
SQL_STATISTIQUES   = SQL_STATISTIQUES.format(**_FILTRES)
SQL_SANS_CLEF      = SQL_SANS_CLEF.format(**_FILTRES)
SQL_LIGNES_MORTES  = SQL_LIGNES_MORTES.format(**_FILTRES)
SQL_GEOMETRIES_LOURDES = SQL_GEOMETRIES_LOURDES.format(**_FILTRES)
SQL_NOMS_ESPACES   = SQL_NOMS_ESPACES.format(**_FILTRES)
SQL_CLEF_BIGINT    = SQL_CLEF_BIGINT.format(**_FILTRES)


def _colonne_existe(curseur, oid, nom):
    """Une colonne de ce nom est-elle deja presente ?"""
    curseur.execute(
        'SELECT 1 FROM pg_attribute WHERE attrelid = %s AND attname = %s '
        'AND attnum > 0 AND NOT attisdropped', (oid, nom),
    )
    return curseur.fetchone() is not None


def _colonne_utilisable(curseur, oid, cible, lignes):
    """Cherche une colonne entiere qui pourrait servir de clef.

    Retourne (nom, utilisable, type). Un nom sans utilisable signifie
    qu'une colonne plausible existe mais porte des doublons ou des valeurs
    nulles — l'information vaut la peine d'etre dite a l'utilisateur.

    L'unicite se verifie sur les donnees, pas sur le schema : une colonne
    « id » sans contrainte contient presque toujours des valeurs uniques,
    et la declarer coute infiniment moins cher que d'ajouter une colonne.
    """
    if lignes > SEUIL_VERIFICATION_UNICITE:
        return None, False, None   # trop gros pour verifier a bon compte

    curseur.execute(SQL_CANDIDATS, (oid,))
    candidats = curseur.fetchall()
    premier = None
    for nom, non_nulle, typname in candidats:
        colonne = citer(nom)
        try:
            # Identifiants cites par citer() et cible_sql() ; aucune valeur
            # fournie par l'utilisateur n'entre dans cette requete.
            curseur.execute(
                f'SELECT count(*), count(DISTINCT {colonne}), '  # nosec B608
                f'count(*) - count({colonne}) FROM {cible}'
            )
            total, distincts, nuls = curseur.fetchone()
        except Exception:
            continue
        if total and total == distincts and not nuls:
            return nom, True, typname
        if premier is None:
            premier = nom
    return premier, False, None


def diagnostiquer(curseur, journal=None):
    """Interroge la base et retourne la liste des problemes constates.

    `curseur` est un curseur DBAPI ; `journal` un callable optionnel pour
    suivre l'avancement. Aucune ecriture n'est faite.
    """
    def dire(message):
        if journal:
            journal(message)

    problemes = []

    # ── Index spatiaux ────────────────────────────────────────────────
    dire('Recherche des index spatiaux manquants…')
    curseur.execute(SQL_SANS_INDEX)
    for schema, table, geom, lignes in curseur.fetchall():
        index = nom_index(table, geom)
        problemes.append(Probleme(
            table, schema,
            'Index spatial manquant',
            f'La colonne « {geom} » n\'a pas d\'index GIST. '
            + (f'Chaque affichage lit les {lignes} lignes de la table.'
               if lignes > 0 else
               'Chaque affichage lit la table entière.'),
            GRAVE,
            sql=(f'CREATE INDEX IF NOT EXISTS {citer(index)} '
                 f'ON {cible_sql(schema, table)} USING GIST ({citer(geom)})'),
            automatique=True,
            annulation=f'DROP INDEX {citer(schema)}.{citer(index)}',
        ))

    # ── Clefs primaires ───────────────────────────────────────────────
    dire('Vérification des clefs primaires…')
    curseur.execute(SQL_SANS_CLEF)
    for schema, table, oid, lignes, a_une_clef in curseur.fetchall():
        cible = cible_sql(schema, table)
        colonne, unique, typcol = _colonne_utilisable(curseur, oid, cible, lignes)

        if colonne and unique:
            # Une colonne convient deja : la declarer coute un index, pas
            # une reecriture de la table, et n'ajoute rien aux formulaires.
            # Une clef en bigint est refusee par QGIS Serveur : la
            # convertir doit faire partie de la meme correction, sinon on
            # remplace un defaut par le suivant.
            conversion = ''
            if typcol == 'int8':
                conversion = (f'ALTER TABLE {cible} '
                              f'ALTER COLUMN {citer(colonne)} TYPE integer;\n')

            if a_une_clef:
                index = nom_index(table, colonne, 'unique')
                correction = (conversion +
                              f'CREATE UNIQUE INDEX IF NOT EXISTS '
                              f'{citer(index)} ON {cible} ({citer(colonne)})')
                annulation = f'DROP INDEX {citer(schema)}.{citer(index)}'
                consequence = (f'Déclare « {colonne} », qui contient déjà des '
                               'valeurs uniques, comme identifiant utilisable '
                               'par QGIS. La clef primaire existante, non '
                               'entière, est conservée.')
            else:
                # Nommer la contrainte plutot que de deviner le nom que
                # PostgreSQL lui donnerait : l'annulation devient exacte.
                contrainte = nom_index(table, colonne, 'pkey')
                correction = (conversion +
                              f'ALTER TABLE {cible} ADD CONSTRAINT '
                              f'{citer(contrainte)} PRIMARY KEY '
                              f'({citer(colonne)})')
                annulation = (f'ALTER TABLE {cible} DROP CONSTRAINT '
                              f'{citer(contrainte)}')
                consequence = (f'Déclare « {colonne} », qui contient déjà des '
                               'valeurs uniques, comme clef primaire. Aucune '
                               'colonne ajoutée.')
            detail = (f'La colonne « {colonne} » contient déjà des valeurs '
                      'uniques et non nulles, mais rien ne le déclare : QGIS '
                      "l'ignore et lit toute la table pour fabriquer ses "
                      "identifiants d'entité.")
            if conversion:
                detail += (" Elle est de type bigint : la correction la "
                           "convertit d'abord en integer, sans quoi QGIS "
                           'Serveur refuserait la clef.')
                consequence = ('Convertit la colonne de bigint en integer, '
                               'ce qui réécrit la table, puis ' +
                               consequence[0].lower() + consequence[1:])
        else:
            nouvelle = 'fid' if not _colonne_existe(curseur, oid, 'fid') else 'fid_qgis'
            if a_une_clef:
                # serial et non bigserial : bigserial produit un int8,
                # que QGIS Serveur refuse comme clef primaire.
                correction = (f'ALTER TABLE {cible} '
                              f'ADD COLUMN {citer(nouvelle)} serial '
                              'NOT NULL UNIQUE')
                annulation = (f'ALTER TABLE {cible} '
                              f'DROP COLUMN {citer(nouvelle)}')
                consequence = (f'Ajoute une colonne « {nouvelle} » entière et '
                               'unique. La clef primaire existante, non '
                               'entière, est conservée.')
            else:
                contrainte = nom_index(table, nouvelle, 'pkey')
                correction = (f'ALTER TABLE {cible} '
                              f'ADD COLUMN {citer(nouvelle)} serial, '
                              f'ADD CONSTRAINT {citer(contrainte)} '
                              f'PRIMARY KEY ({citer(nouvelle)})')
                annulation = (f'ALTER TABLE {cible} '
                              f'DROP COLUMN {citer(nouvelle)}')
                consequence = (f'Ajoute une colonne « {nouvelle} » comme clef '
                               'primaire.')
            manque = ('aucune colonne entière ne convient'
                      if colonne is None else
                      f'la colonne « {colonne} » contient des doublons ou des '
                      'valeurs nulles')
            detail = (f'QGIS lit toute la table pour fabriquer ses identifiants '
                      f"d'entité : {manque}. L'édition et la collecte QField "
                      'en dépendent aussi.')

        problemes.append(Probleme(
            table, schema,
            'Pas de clef primaire entière',
            detail, GRAVE,
            sql=correction,
            confirmable=True,
            consequence=(consequence + " La table est verrouillée le temps de "
                         "l'opération."),
            annulation=annulation,
        ))

    # ── Clefs primaires en bigint ─────────────────────────────────────
    dire('Contrôle du type des clefs primaires…')
    curseur.execute(SQL_CLEF_BIGINT)
    for schema, table, colonne, oid, lignes, referencee in curseur.fetchall():
        cible = cible_sql(schema, table)
        # Convertir n'a de sens que si les valeurs tiennent dans un int4 et
        # qu'aucune clef etrangere ne pointe vers la colonne : sinon il
        # faudrait aussi convertir les tables qui la referencent.
        tient = None
        try:
            # Identifiants cites par citer() et cible_sql() ; aucune
            # valeur exterieure n'entre dans cette requete.
            curseur.execute(
                f'SELECT COALESCE(MAX({citer(colonne)}), 0) '  # nosec B608
                f'FROM {cible}'
            )
            tient = (curseur.fetchone()[0] or 0) <= MAX_INT4
        except Exception:
            tient = None

        convertible = bool(tient) and not referencee
        if convertible:
            correction = (f'ALTER TABLE {cible} '
                          f'ALTER COLUMN {citer(colonne)} TYPE integer')
            consequence = (
                f'Convertit « {colonne} » de bigint en integer. La table est '
                'réécrite et reste verrouillée pendant l\'opération ; les '
                'valeurs sont conservées.'
            )
            annulation = (f'ALTER TABLE {cible} '
                          f'ALTER COLUMN {citer(colonne)} TYPE bigint')
        else:
            correction = (f'-- Conversion a examiner a la main :\n'
                          f'ALTER TABLE {cible} '
                          f'ALTER COLUMN {citer(colonne)} TYPE integer;')
            consequence = ''
            annulation = ''

        if referencee:
            obstacle = ("d'autres tables référencent cette colonne : elles "
                        'doivent être converties en même temps')
        elif tient is False:
            obstacle = ('certaines valeurs dépassent la capacité d\'un entier '
                        '32 bits')
        elif tient is None:
            obstacle = "la table n'a pas pu être lue"
        else:
            obstacle = ''

        detail = (
            f'La clef primaire « {colonne} » est un bigint. QGIS Serveur '
            'attend un entier 32 bits : le zoom sur une entité et le '
            'filtrage cessent de fonctionner dans Lizmap.'
        )
        if obstacle:
            detail += f' Conversion non automatisable : {obstacle}.'

        problemes.append(Probleme(
            table, schema,
            'Clef primaire en bigint',
            detail, GRAVE,
            sql=correction,
            confirmable=convertible,
            consequence=consequence,
            annulation=annulation,
        ))

    # ── Statistiques ──────────────────────────────────────────────────
    dire('Contrôle des statistiques…')
    curseur.execute(SQL_STATISTIQUES)
    for schema, table, lignes, modifs, jamais in curseur.fetchall():
        motif = ('aucune statistique n\'a jamais été calculée'
                 if jamais else
                 f'{modifs} lignes modifiées depuis le dernier calcul')
        problemes.append(Probleme(
            table, schema,
            'Statistiques à rafraîchir',
            f'{motif.capitalize()}. Sans statistiques à jour, PostgreSQL '
            'ignore souvent les index disponibles.',
            MOYEN,
            sql=f'ANALYZE {cible_sql(schema, table)}',
            automatique=True,
        ))

    # ── Lignes mortes ─────────────────────────────────────────────────
    dire('Recherche des lignes mortes…')
    curseur.execute(SQL_LIGNES_MORTES)
    for schema, table, vivantes, mortes in curseur.fetchall():
        problemes.append(Probleme(
            table, schema,
            'Espace mort à récupérer',
            f'{mortes} lignes mortes pour {vivantes} vivantes. '
            'La table est lue plus longtemps qu\'elle ne le devrait.',
            MINEUR,
            sql=f'VACUUM ANALYZE {cible_sql(schema, table)}',
            automatique=True,
        ))

    # ── Geometries trop detaillees ────────────────────────────────────
    dire('Mesure du détail des polygones…')
    curseur.execute(SQL_GEOMETRIES_LOURDES)
    for schema, table, geom in curseur.fetchall():
        cible = cible_sql(schema, table)
        try:
            curseur.execute(SQL_SOMMETS.format(geom=citer(geom), cible=cible))
            sommets = curseur.fetchone()[0] or 0
        except Exception:
            continue
        if sommets < SEUIL_SOMMETS:
            continue
        decoupee = cible_sql(schema, table + '_decoupee')
        problemes.append(Probleme(
            table, schema,
            'Polygones très détaillés',
            f'Jusqu\'à {sommets} sommets pour une seule entité. Sa boîte '
            'englobante couvre une large zone : l\'index spatial ne filtre '
            'plus rien. Un découpage par ST_Subdivide accélère nettement.',
            MOYEN,
            # Suggestion affichee a l'utilisateur, jamais executee par le
            # plugin : ce probleme porte automatique=False. Les identifiants
            # y sont malgre tout cites par citer(), qui double les
            # guillemets internes.
            sql=(f'-- Table dérivée, à substituer dans le projet :\n'  # nosec B608
                 f'CREATE TABLE {decoupee} AS\n'
                 f'  SELECT *, ST_Subdivide({citer(geom)}, 256) AS geom_decoupee\n'
                 f'  FROM {cible};\n'
                 f'CREATE INDEX ON {decoupee} USING GIST (geom_decoupee);'),
            automatique=False,   # cree une table : decision de modelisation
        ))

    # ── Noms de table ─────────────────────────────────────────────────
    dire('Contrôle des noms de table…')
    curseur.execute(SQL_NOMS_ESPACES)
    for schema, table in curseur.fetchall():
        propre = table.strip()
        problemes.append(Probleme(
            table, schema,
            'Nom de table avec espace',
            f'Le nom « {table} » commence ou finit par une espace. Il doit '
            'être cité partout, et deux tables peuvent ne différer que par '
            'une espace invisible.',
            MINEUR,
            sql=(f'-- Renommer casse les projets qui référencent l\'ancien nom.\n'
                 f'ALTER TABLE {cible_sql(schema, table)} '
                 f'RENAME TO {citer(propre)};'),
            automatique=False,   # renommer casserait les projets existants
        ))

    ordre = {GRAVE: 0, MOYEN: 1, MINEUR: 2}
    problemes.sort(key=lambda p: (ordre[p.gravite], p.cible))
    return problemes


def _niveau(probleme):
    """Comment la correction sera appliquee, en clair."""
    if probleme.automatique:
        return 'Automatique'
    if probleme.confirmable:
        return 'Sur confirmation'
    return 'A la main'


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
    graveur.writerow(['Instance', instance, 'Base', base])
    graveur.writerow([
        'Gravite', 'Schema', 'Table', 'Probleme', 'Correction',
        'Detail', 'SQL', 'Consequence', 'Annulation',
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
        '-- Diagnostic de la base LizPack',
        f'-- Instance : {instance}',
        f'-- Base     : {base}',
        f'-- Genere   : {datetime.datetime.now():%Y-%m-%d %H:%M}',
        f'-- {len(problemes)} point(s) releve(s)',
        '--',
        '-- Les corrections « a la main » sont commentees : relisez-les',
        '-- avant de les activer.',
        '',
    ]
    ordre = [
        ('Corrections sans risque', lambda p: p.automatique),
        ('Corrections a confirmer', lambda p: p.confirmable),
        ('A traiter a la main', lambda p: not p.applicable),
    ]
    for titre, garde in ordre:
        lot = [p for p in problemes if garde(p)]
        if not lot:
            continue
        lignes += ['-- ' + '=' * 68, f'-- {titre} ({len(lot)})',
                   '-- ' + '=' * 68, '']
        for p in lot:
            lignes.append(f'-- {p.cible} — {p.titre}')
            lignes.append(f'--    {p.detail}')
            if p.consequence:
                lignes.append(f'--    Consequence : {p.consequence}')
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
                lignes.append(f'--    Pour defaire : {p.annulation};')
            lignes.append('')
    return '\n'.join(lignes)


def appliquer(connexion, problemes, journal=None):
    """Applique les corrections marquees comme sures.

    Chaque instruction est jouee isolement : une table verrouillee ou
    disparue ne doit pas faire echouer les autres. Retourne
    (reussies, echouees).
    """
    def dire(message):
        if journal:
            journal(message)

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
                except Exception:
                    pass
    finally:
        connexion.autocommit = ancien_autocommit
    return reussies, echouees
