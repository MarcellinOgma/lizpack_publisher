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
reprojection.py
───────────────
Ramene les couches d'un projet dans un systeme de coordonnees unique.

Le serveur refuse un projet dont les couches ne partagent pas la meme
projection : chacune des couches divergentes serait reprojetee a la volee, a
chaque affichage, pour chaque visiteur de la carte. Plutot que de renvoyer
l'utilisateur faire l'operation a la main, le plugin la propose au moment ou
le refus surviendrait.

Le projet est corrige SUR PLACE, sous son propre nom : c'est lui que
l'utilisateur rouvrira, lui qu'il republiera, et une copie parallele n'aurait
fait que dedoubler le probleme sans jamais le resoudre.

Avant toute ecriture, une sauvegarde « <projet>.qgs.bak » est posee a cote.
C'est elle qui permet de revenir en arriere si le resultat ne convient pas.
"""
import os
from .i18n import tr
import shutil

from . import journal

# Couches dont la projection est imposee par le service distant. Une tuile XYZ
# est toujours en 3857 ; la reprojeter n'aurait aucun sens, et le serveur les
# ecarte deja de son controle.
FOURNISSEURS_FOND_DE_CARTE = ('wms', 'xyz', 'wmts', 'wcs', 'vectortile', 'arcgismapserver',
                              'arcgisfeatureserver')


def _est_fond_de_carte(couche):
    fournisseur = ''
    try:
        fournisseur = (couche.dataProvider().name() or '').lower()
    except Exception as e:
        journal.ignorer(e, 'lecture du fournisseur de la couche')
    if fournisseur in FOURNISSEURS_FOND_DE_CARTE:
        return True
    # Une couche raster distante n'annonce pas toujours son type par le
    # fournisseur : sa source le dit.
    source = ''
    try:
        source = (couche.source() or '').lower()
    except Exception as e:
        journal.ignorer(e, 'lecture de la source de la couche')
    return 'type=xyz' in source or 'type=wmts' in source


def inventaire(projet):
    """Rend {authid: [couches]} pour les couches de donnees du projet.

    Meme perimetre que le controle du serveur — fonds de carte et couches sans
    geometrie exclus — pour que les deux voient la meme chose.
    """
    from qgis.core import QgsMapLayer, QgsWkbTypes

    par_projection = {}
    for couche in projet.mapLayers().values():
        if couche.type() != QgsMapLayer.VectorLayer:
            continue
        if _est_fond_de_carte(couche):
            continue
        try:
            if couche.geometryType() == QgsWkbTypes.NullGeometry:
                continue        # table attributaire : rien a projeter
        except Exception as e:
            journal.ignorer(e, 'lecture du type de geometrie')
            continue
        authid = couche.crs().authid()
        if authid:
            par_projection.setdefault(authid, []).append(couche)
    return par_projection


def projection_cible(projet, par_projection):
    """La projection vers laquelle tout ramener.

    Celle du projet si elle figure deja parmi les couches — c'est le repere
    dans lequel le serveur composera la carte —, sinon la plus repandue :
    c'est elle qui demande le moins de conversions.
    """
    crs_projet = projet.crs().authid()
    if crs_projet and crs_projet in par_projection:
        return crs_projet
    if not par_projection:
        return crs_projet
    return max(par_projection, key=lambda c: len(par_projection[c]))


def _est_postgis(couche):
    try:
        return (couche.dataProvider().name() or '').lower() == 'postgres'
    except Exception as e:
        journal.ignorer(e, 'lecture du fournisseur de la couche')
        return False


def couches_a_reprojeter(projet):
    """Rend (cible, a_convertir, en_base) pour les couches divergentes.

    Les couches PostGIS sont mises a part : les exporter en GeoPackage
    sortirait les donnees de la base, ce qui n'est pas une correction mais un
    deplacement. Une table se reprojette EN BASE — le rapport du serveur donne
    la commande — et le plugin se contente de le dire.
    """
    par_projection = inventaire(projet)
    if len(par_projection) < 2:
        return projection_cible(projet, par_projection), [], []
    cible = projection_cible(projet, par_projection)
    divergentes = [c for authid, couches in par_projection.items()
                   if authid != cible for c in couches]
    a_convertir = [c for c in divergentes if not _est_postgis(c)]
    en_base = [c for c in divergentes if _est_postgis(c)]
    return cible, a_convertir, en_base


def _destination(couche):
    """Chemin du fichier reprojete : le meme nom, en GeoPackage.

    Aucun code EPSG dans le nom. Le projet ne doit pas se retrouver entoure de
    fichiers dont le nom rappelle une conversion : ce qui compte est que la
    donnee soit juste, pas la maniere dont elle l'est devenue.
    """
    source = couche.source().split('|')[0]
    base, _ext = os.path.splitext(source)
    if not base or not os.path.isabs(base):
        base = os.path.join(os.path.expanduser('~'), couche.name())
    return f'{base}.gpkg'


def reprojeter(couche, cible, destination=None, journal_avancement=None):
    """Ecrit une copie de la couche dans le systeme `cible`.

    Rend (chemin, message d'erreur). L'original n'est jamais modifie.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem, QgsCoordinateTransform,
        QgsCoordinateTransformContext, QgsVectorFileWriter, QgsProject,
    )

    crs = QgsCoordinateReferenceSystem(cible)
    if not crs.isValid():
        return None, tr('Le système de coordonnées {0} est inconnu de QGIS.', cible)

    destination = destination or _destination(couche)
    if journal_avancement:
        journal_avancement(f'{couche.name()} → {cible}…')

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = couche.name()
    # SANS transformation, l'ecriture se contenterait de RECOPIER la couche
    # dans son systeme d'origine : c'est `ct` qui reprojette, et rien d'autre.
    options.ct = QgsCoordinateTransform(
        couche.crs(), crs, QgsProject.instance())
    # Le fichier peut deja exister d'une conversion precedente : on le
    # remplace plutot que d'empiler les couches dans la meme archive.
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    try:
        resultat = QgsVectorFileWriter.writeAsVectorFormatV3(
            couche, destination,
            QgsProject.instance().transformContext()
            if hasattr(QgsProject.instance(), 'transformContext')
            else QgsCoordinateTransformContext(),
            options,
        )
    except TypeError:
        # QGIS 3.10 a 3.20 : signature precedente, sans contexte de
        # transformation. Le plugin doit fonctionner sur les deux.
        # `crs` en quatrieme position est bien le systeme de DESTINATION :
        # cette signature reprojette.
        resultat = QgsVectorFileWriter.writeAsVectorFormat(
            couche, destination, 'UTF-8', crs, 'GPKG')
    except Exception as e:
        return None, str(e)

    # Selon la version, le premier element est un code d'erreur ou un tuple.
    code = resultat[0] if isinstance(resultat, (tuple, list)) else resultat
    if code != QgsVectorFileWriter.NoError:
        detail = ''
        if isinstance(resultat, (tuple, list)) and len(resultat) > 1:
            detail = str(resultat[1] or '')
        return None, detail or tr('Écriture impossible (code {0}).', code)

    return destination, ''



def _sauvegarder(chemin, journal_avancement=None):
    """Pose un « .bak » a cote du fichier, et rend son chemin (ou None)."""
    sauvegarde = f'{chemin}.bak'
    try:
        shutil.copy2(chemin, sauvegarde)
        if journal_avancement:
            journal_avancement(tr('Sauvegarde : {0}', os.path.basename(sauvegarde)))
        return sauvegarde
    except Exception as e:  # noqa: BLE001
        journal.ignorer(e, f'sauvegarde de {chemin}')
        return None


def uniformiser(projet, cible, couches, journal_avancement=None):
    """Ramene les couches vers `cible` et enregistre le projet sous son nom.

    Le projet garde son fichier, son nom et son adresse : c'est lui que
    l'utilisateur rouvrira et republiera. Une sauvegarde « .bak » est posee
    avant toute ecriture — du projet, et de chaque fichier de donnees qui se
    trouverait remplace.

    Rend (reussies, echouees) ; `echouees` liste des (nom, motif).
    """
    from qgis.core import QgsCoordinateReferenceSystem

    crs = QgsCoordinateReferenceSystem(cible)
    if not crs.isValid():
        return [], [('projet', tr('Le système {0} est inconnu de QGIS.', cible))]

    chemin_projet = projet.fileName()
    if chemin_projet:
        _sauvegarder(chemin_projet, journal_avancement)

    reussies, echouees = [], []
    for couche in couches:
        nom = couche.name()
        if journal_avancement:
            journal_avancement(tr('Reprojection de « {0} »…', nom))
        try:
            source = couche.source().split('|')[0]
            destination = _destination(couche)

            # La couche s'ecrit sous le nom qu'elle porte deja : on passe par
            # un fichier intermediaire, car GDAL ne peut pas lire et ecrire le
            # meme GeoPackage dans le meme mouvement.
            memes_fichiers = os.path.normcase(source) == os.path.normcase(destination)
            # Le nom provisoire doit garder l'extension du format : GDAL
            # ajoute celle du pilote quand elle manque, si bien qu'un
            # « .gpkg.reproj » devenait « .gpkg.reproj.gpkg » et que le
            # remplacement portait sur un fichier inexistant.
            racine, _ = os.path.splitext(destination)
            provisoire = f'{racine}_reproj_tmp.gpkg' if memes_fichiers else destination

            # Un GeoPackage homonyme peut deja exister sans etre la source de
            # la couche : il va etre remplace, il lui faut sa sauvegarde.
            if not memes_fichiers and os.path.exists(destination):
                _sauvegarder(destination, journal_avancement)

            chemin, erreur = reprojeter(couche, cible, destination=provisoire)
            if erreur:
                echouees.append((nom, erreur))
                continue

            if memes_fichiers:
                # Windows verrouille tout fichier qu'une couche tient ouvert.
                # On detache donc la couche vers l'intermediaire pour liberer
                # l'original, puis on RECOPIE l'intermediaire par-dessus : le
                # deplacer echouerait, puisque la couche le tient a son tour.
                couche.setDataSource(f'{provisoire}|layername={nom}', nom, 'ogr')
                _sauvegarder(destination, journal_avancement)
                shutil.copy2(provisoire, destination)

            couche.setDataSource(f'{destination}|layername={nom}', nom, 'ogr')

            if memes_fichiers:
                # La couche pointe a nouveau sur le fichier definitif :
                # l'intermediaire n'est plus tenu et peut disparaitre. S'il
                # resiste encore, il ne gene personne — on n'echoue pas pour si
                # peu apres une conversion reussie.
                try:
                    os.remove(provisoire)
                except OSError as e:
                    journal.ignorer(e, 'suppression du fichier intermediaire')
            couche.setCrs(crs)
            reussies.append(nom)
        except Exception as e:  # noqa: BLE001
            echouees.append((nom, str(e)))

    if reussies:
        # Le projet doit annoncer la meme projection que ses couches, sinon on
        # remplacerait le melange par un desaccord entre projet et donnees.
        projet.setCrs(crs)
        if chemin_projet:
            projet.write()

    return reussies, echouees
