"""
plugin.py
─────────
Point d'entrée du plugin QGIS LizPack Publisher v2.
"""
import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QFontMetrics
from qgis.PyQt.QtCore import Qt, QRectF
from qgis.PyQt.QtSvg import QSvgRenderer


def _lizpack_icon():
    """Génère l'icône LizPack (carte pliée verte) depuis le SVG intégré."""
    plugin_dir = os.path.dirname(__file__)
    svg_path = os.path.join(plugin_dir, 'icon.svg')
    if os.path.exists(svg_path):
        renderer = QSvgRenderer(svg_path)
        if renderer.isValid():
            pm = QPixmap(64, 64)
            pm.fill(Qt.transparent)
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
            self.dialog.close()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            from .dialog import LizpackDialog
            self.dialog = LizpackDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
