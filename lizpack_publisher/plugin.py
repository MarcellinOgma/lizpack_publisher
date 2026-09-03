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
plugin.py
─────────
Point d'entrée du plugin QGIS LizPack Publisher v2.
"""
import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtSvg import QSvgRenderer


def _lizpack_icon():
    """Génère l'icône LizPack (carte pliée verte) depuis le SVG intégré."""
    plugin_dir = os.path.dirname(__file__)
    svg_path = os.path.join(plugin_dir, 'icon.svg')
    if os.path.exists(svg_path):
        renderer = QSvgRenderer(svg_path)
        if renderer.isValid():
            pm = QPixmap(64, 64)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            renderer.render(p)
            p.end()
            return QIcon(pm)

    # Fallback : icône PNG
    png_path = os.path.join(plugin_dir, 'icon.png')
    if os.path.exists(png_path):
        return QIcon(png_path)

    return QIcon()


class LizpackPublisherPlugin:

    def __init__(self, iface):
        self.iface  = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = _lizpack_icon()
        self.action = QAction(icon, 'LizPack Publisher', self.iface.mainWindow())
        self.action.setToolTip('Publier et gérer vos projets QGIS sur LizPack')
        self.action.triggered.connect(self.run)

        self.iface.addPluginToWebMenu('LizPack', self.action)
        self.iface.addWebToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginWebMenu('LizPack', self.action)
        self.iface.removeWebToolBarIcon(self.action)
        if self.dialog:
            # close() met les fils encore actifs a l'abri (voir closeEvent) et
            # debranche le signal de projet : sans cela QGIS appellerait une
            # methode d'une fenetre detruite au prochain projet ouvert.
            self.dialog.close()
            self.dialog.detacher_de_qgis()
            # close() ne fait que masquer : la fenetre reste rattachee a la
            # fenetre principale de QGIS et survit au dechargement. Sans ces
            # deux lignes, chaque reinstallation ou mise a jour du plugin
            # laissait derriere elle une fenetre fantome, encore connectee,
            # que l'utilisateur retrouvait a cote de la nouvelle.
            self.dialog.setParent(None)
            self.dialog.deleteLater()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            from .dialog import LizpackDialog
            self.dialog = LizpackDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
