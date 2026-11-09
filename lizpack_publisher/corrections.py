# LizPack Publisher — plugin QGIS pour les instances LizPack
# Copyright (C) 2026 GEODONNÉE INC
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et le
# modifier selon les termes de la Licence publique générale GNU publiée par
# la Free Software Foundation, en version 3 ou toute version ultérieure.
#
# Il est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE
# GARANTIE. Voyez la Licence publique générale GNU pour plus de détails.
"""
corrections.py
──────────────
Ce que le plugin sait corriger lui-même dans le projet ouvert, à la suite
d'une validation : plutôt que de renvoyer l'utilisateur faire l'opération à
la main dans QGIS, il la lui propose et la fait.

Le plan est établi d'après l'état RÉEL du projet, pas d'après le texte du
rapport (traduit, il ne se lirait plus) : ce que le serveur signale, le
plugin le retrouve dans le projet et le corrige.

  - projet sans système de coordonnées : celui des couches ;
  - couches toutes dans une projection autre que celle du projet : le projet
    passe dans la leur (aucune donnée touchée) ;
  - projections mélangées : fichiers reprojetés (reprojection.py), tables
    PostGIS reprojetées EN BASE (ST_Transform) ;
  - étendue nulle ou incohérente : recalculée ;
  - couche lourde dessinée à toutes les échelles : limitée au 1:50 000.
"""
from .i18n import tr
from . import journal
from . import reprojection

# Mêmes seuils que le validateur du serveur (qgs_validator.py).
SEUIL_OBJETS_LOURDE = 100_000
ECHELLE_MAX_COUCHE_LOURDE = 50_000


class Correction:
    def __init__(self, description, appliquer, modifie_donnees=False):
        self.description = description
        self.appliquer = appliquer          # () -> None, lève en cas d'échec
        self.modifie_donnees = modifie_donnees


def _couches_vecteur(projet):
    from qgis.core import QgsMapLayer
    return [c for c in projet.mapLayers().values() if c.type() == QgsMapLayer.VectorLayer]


def _reprojeter_table(couche, cible):
    """Reprojette la table PostGIS d'une couche, dans la base."""
    from qgis.core import (QgsDataSourceUri, QgsProviderRegistry,
                           QgsCoordinateReferenceSystem)
    uri = QgsDataSourceUri(couche.source())
    schema, table, colonne = uri.schema() or 'public', uri.table(), uri.geometryColumn()
    srid = int(cible.split(':', 1)[1])
    meta = QgsProviderRegistry.instance().providerMetadata('postgres')
    cnx = meta.createConnection(uri.uri(False), {})

    def lit(v):
        return "'" + str(v).replace("'", "''") + "'"

    def ident(v):
        return '"' + str(v).replace('"', '""') + '"'

    lignes = cnx.executeSql(
        'SELECT type FROM geometry_columns WHERE f_table_schema = {} AND '
        'f_table_name = {} AND f_geometry_column = {}'.format(lit(schema), lit(table), lit(colonne)))
    typ = (lignes[0][0] if lignes and lignes[0] else '') or 'Geometry'
    cnx.executeSql(
        'ALTER TABLE {s}.{t} ALTER COLUMN {c} TYPE geometry({typ}, {srid}) '
        'USING ST_Transform({c}, {srid})'.format(
            s=ident(schema), t=ident(table), c=ident(colonne), typ=typ, srid=srid))
    uri.setSrid(str(srid))
    couche.setDataSource(uri.uri(False), couche.name(), 'postgres')
    couche.setCrs(QgsCoordinateReferenceSystem(cible))


def plan(projet):
    """Les corrections applicables au projet ouvert."""
    from qgis.core import QgsCoordinateReferenceSystem
    out = []
    par_projection = reprojection.inventaire(projet)
    crs_projet = projet.crs().authid() if projet.crs().isValid() else ''

    if len(par_projection) == 1:
        seule = next(iter(par_projection))
        if seule != crs_projet:
            out.append(Correction(
                tr('Passer le projet en {0}, la projection de ses couches.', seule),
                lambda s=seule: projet.setCrs(QgsCoordinateReferenceSystem(s))))
    elif len(par_projection) > 1:
        cible, fichiers, tables = reprojection.couches_a_reprojeter(projet)
        if not crs_projet:
            out.append(Correction(
                tr('Définir le système de coordonnées du projet : {0}.', cible),
                lambda c=cible: projet.setCrs(QgsCoordinateReferenceSystem(c))))
        if fichiers:
            noms = ', '.join(c.name() for c in fichiers)

            def _fichiers(c=cible, l=list(fichiers)):
                _, echouees = reprojection.uniformiser(projet, c, l)
                if echouees:
                    raise Exception('; '.join('{} : {}'.format(n, m) for n, m in echouees))
            out.append(Correction(
                tr('Reprojeter en {0} les fichiers de : {1} (sauvegarde « .bak » à côté).', cible, noms),
                _fichiers, modifie_donnees=True))
        vues = set()
        for couche in tables:
            cle = couche.source()
            if cle in vues:
                continue
            vues.add(cle)
            out.append(Correction(
                tr('Reprojeter en {0} la table PostGIS de « {1} », dans la base.', cible, couche.name()),
                lambda c=couche, ci=cible: _reprojeter_table(c, ci), modifie_donnees=True))

    for couche in _couches_vecteur(projet):
        try:
            e = couche.extent()
            if couche.featureCount() > 0 and (e.isNull() or e.isEmpty()
                                              or e.xMinimum() > e.xMaximum()
                                              or e.yMinimum() > e.yMaximum()):
                out.append(Correction(
                    tr("Recalculer l'étendue de « {0} ».", couche.name()),
                    lambda c=couche: c.updateExtents(True)))
        except Exception as ex:
            journal.ignorer(ex, "lecture de l'étendue d'une couche")
        try:
            n = couche.featureCount()
            limite = couche.hasScaleBasedVisibility() and 0 < couche.minimumScale() <= ECHELLE_MAX_COUCHE_LOURDE
            if n >= SEUIL_OBJETS_LOURDE and not limite:
                def _echelle(c=couche):
                    c.setScaleBasedVisibility(True)
                    c.setMinimumScale(ECHELLE_MAX_COUCHE_LOURDE)
                out.append(Correction(
                    tr('Limiter « {0} » ({1} objets) aux échelles plus grandes que 1:50 000.', couche.name(), n),
                    _echelle))
        except Exception as ex:
            journal.ignorer(ex, "lecture du nombre d'objets d'une couche")
    return out
