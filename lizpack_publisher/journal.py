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
journal.py
──────────
Trace les erreurs sans valeur pour l'utilisateur.

Certaines defaillances ne meritent pas d'interrompre le travail :
fermer une connexion deja fermee, lire une date illisible, poser un
reglage qu'une version ancienne de QGIS ignore. Les avaler en silence
est pourtant ce qui a masque, dans ce plugin, une AttributeError qui
privait chaque projet publie de sa reecriture PostGIS.

`ignorer()` est le compromis : le travail continue, mais la trace part
dans le journal des messages de QGIS, ou elle reste consultable quand
quelque chose se comporte etrangement.
"""

try:
    from qgis.core import QgsMessageLog, Qgis
except ImportError:      # hors de QGIS — tests, outillage
    QgsMessageLog = None
    Qgis = None

ETIQUETTE = 'LizPack Publisher'


def ignorer(erreur, contexte=''):
    """Note une erreur benigne et laisse le programme poursuivre.

    A n'employer que lorsque la suite du traitement reste correcte sans
    l'operation qui a echoue. Tout le reste doit remonter.
    """
    if QgsMessageLog is None:
        return
    message = f'{contexte} : {erreur}' if contexte else str(erreur)
    QgsMessageLog.logMessage(message, ETIQUETTE, Qgis.Info)
