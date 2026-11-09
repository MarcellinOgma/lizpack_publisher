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
dialog.py
─────────
Interface professionnelle LIZPACK Publisher v2.
Icônes SVG (Feather Icons), palette navy/bleu, design carte.
Flow : email + password → JWT → dropdown instances → connexion instance
"""
import os
from .i18n import tr
import tempfile
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QHeaderView, QAbstractItemView,
    QSizePolicy, QFrame, QMenu, QInputDialog, QMessageBox, QApplication,
    QCheckBox, QListView, QSplitter,
)
from qgis.PyQt.QtCore import (
    Qt, QByteArray, QSize, QTimer, QUrl, QSettings, QEvent,
)
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QCursor, QColor
from qgis.PyQt.QtSvg import QSvgRenderer

from qgis.core import (
    QgsProject, QgsDataSourceUri, QgsVectorLayer,
    QgsApplication, QgsAuthMethodConfig, QgsProviderRegistry,
)

from . import journal
from . import liaison_bd
from .api_client import LizpackSession
from .session_entreprise import SessionEntreprise, normaliser_adresse
from .workers import (
    LoginWorker, ConnectInstanceWorker, UploadFolderWorker,
    DownloadProjectWorker, SaveSymbologyWorker, ListFilesWorker,
    DeleteWorker, CreateFolderWorker, RenameWorker, UploadFilesWorker,
    ImportToPostGISWorker, DiagnosticDbWorker, OptimiserDbWorker,
    ListeInstancesWorker, ValidationWorker, ListerTablesWorker,
)


# ══════════════════════════════════════════════════════════════════════════════
# SVG Icon library  —  Feather Icons  (stroke-based, color = {c})
# ══════════════════════════════════════════════════════════════════════════════

_SVG_TPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">{b}</svg>'
)

_SVG = {
    'tool':
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    'lock':
        '<rect x="3" y="11" width="18" height="11" rx="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    'mail':
        '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2'
        'H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>'
        '<polyline points="22,6 12,13 2,6"/>',
    'key':
        '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778'
        ' 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3'
        'm-3.5 3.5L19 4"/>',
    'server':
        '<rect x="2" y="2" width="20" height="8" rx="2"/>'
        '<rect x="2" y="14" width="20" height="8" rx="2"/>'
        '<line x1="6" y1="6" x2="6.01" y2="6"/>'
        '<line x1="6" y1="18" x2="6.01" y2="18"/>',
    'folder':
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5'
        'a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    'folder-upload':
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5'
        'a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
        '<polyline points="15 14 12 11 9 14"/>'
        '<line x1="12" y1="11" x2="12" y2="18"/>',
    'layers':
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>',
    'upload-cloud':
        '<polyline points="16 16 12 12 8 16"/>'
        '<line x1="12" y1="12" x2="12" y2="21"/>'
        '<path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>',
    'copy':
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    'scissors':
        '<circle cx="6" cy="6" r="3"/>'
        '<circle cx="6" cy="18" r="3"/>'
        '<line x1="20" y1="4" x2="8.12" y2="15.88"/>'
        '<line x1="14.47" y1="14.48" x2="20" y2="20"/>'
        '<line x1="8.12" y1="8.12" x2="12" y2="12"/>',
    'clipboard':
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>',
    'database':
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>'
        '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    'link':
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    'log-out':
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        '<polyline points="16 17 21 12 16 7"/>'
        '<line x1="21" y1="12" x2="9" y2="12"/>',
    'refresh':
        '<polyline points="23 4 23 10 17 10"/>'
        '<polyline points="1 20 1 14 7 14"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10'
        'M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    'save':
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 3 7 8 15 8"/>',
    'plus-circle':
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="8" x2="12" y2="16"/>'
        '<line x1="8" y1="12" x2="16" y2="12"/>',
    'check-circle':
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>',
    'x-circle':
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>',
    'file-text':
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/>',
    'map':
        '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>'
        '<line x1="8" y1="2" x2="8" y2="18"/>'
        '<line x1="16" y1="6" x2="16" y2="22"/>',
    'image':
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/>'
        '<polyline points="21 15 16 10 5 21"/>',
    'archive':
        '<polyline points="21 8 21 21 3 21 3 8"/>'
        '<rect x="1" y="3" width="22" height="5"/>'
        '<line x1="10" y1="12" x2="14" y2="12"/>',
    'download':
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>',
    'git-merge':
        '<circle cx="18" cy="18" r="3"/>'
        '<circle cx="6" cy="6" r="3"/>'
        '<path d="M6 21V9a9 9 0 0 0 9 9"/>',
    'alert-circle':
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="8" x2="12" y2="12"/>'
        '<line x1="12" y1="16" x2="12.01" y2="16"/>',
    'browse':
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
        '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    'arrow-left':
        '<line x1="19" y1="12" x2="5" y2="12"/>'
        '<polyline points="12 19 5 12 12 5"/>',
    'folder-plus':
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5'
        'a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
        '<line x1="12" y1="11" x2="12" y2="17"/>'
        '<line x1="9" y1="14" x2="15" y2="14"/>',
    'trash-2':
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
        '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
    'edit-2':
        '<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>',
    'upload':
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>',
    'book-open':
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
        '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    'help-circle':
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>',
    'external-link':
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
        '<polyline points="15 3 21 3 21 9"/>'
        '<line x1="10" y1="14" x2="21" y2="3"/>',
    'message-circle':
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    'zap':
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    'shield':
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    'activity':
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    'chevron-down':
        '<polyline points="6 9 12 15 18 9"/>',
}


def _icon(name: str, color: str = '#4a5568', size: int = 16) -> QIcon:
    """Render an SVG icon to QIcon at the given size.
    Returns an empty QIcon if the name is unknown (no silent failure)."""
    body = _SVG.get(name, '')
    if not body:
        return QIcon()
    svg      = _SVG_TPL.format(c=color, b=body)
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    if not renderer.isValid():
        return QIcon()
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p  = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


def _icone_fichier(name: str, color: str, size: int = 14) -> str:
    """Ecrit une icone sur disque et retourne son chemin pour une feuille QSS.

    Qt ne sait pas peindre une pseudo-propriete `image:` depuis des donnees
    en memoire : il lui faut un fichier. On l'ecrit une fois dans le dossier
    temporaire, sous un nom stable, plutot que dans le dossier du plugin qui
    peut etre en lecture seule.

    Retourne une chaine vide si l'ecriture echoue : la feuille de style
    omettra simplement la regle.
    """
    body = _SVG.get(name, '')
    if not body:
        return ''
    dossier = os.path.join(tempfile.gettempdir(), 'lizpack_publisher_icones')
    chemin  = os.path.join(dossier, f'{name}_{color.lstrip("#")}_{size}.png')
    try:
        os.makedirs(dossier, exist_ok=True)
        if not os.path.isfile(chemin):
            renderer = QSvgRenderer(
                QByteArray(_SVG_TPL.format(c=color, b=body).encode('utf-8'))
            )
            if not renderer.isValid():
                return ''
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            renderer.render(p)
            p.end()
            if not pm.save(chemin, 'PNG'):
                return ''
    except Exception:
        return ''
    # Qt attend des barres obliques dans une feuille de style, y compris
    # sous Windows.
    return chemin.replace(os.sep, '/')


_FLECHE_LISTE = _icone_fichier('chevron-down', '#4a5568', 14)

# Sans fichier, mieux vaut omettre la regle que produire un url() vide,
# que Qt signale et ignore. On retombe alors sur un bouton sans fleche,
# comme avant, plutot que sur une feuille de style bancale.
_QSS_FLECHE = (
    'QComboBox::down-arrow { image: url(%s); width: 14px; height: 14px; }\n'
    'QComboBox::down-arrow:disabled { image: none; }' % _FLECHE_LISTE
    if _FLECHE_LISTE else ''
)


def _letter_icon(letter: str, bg: str, size: int = 20) -> QIcon:
    """Badge carré avec la première lettre en blanc — fiable sur toutes plateformes."""
    from qgis.PyQt.QtGui import QColor, QFont, QBrush, QPen
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p  = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(bg)))
    p.setPen(QPen(Qt.PenStyle.NoPen))
    radius = size * 0.22
    p.drawRoundedRect(0, 0, size, size, radius, radius)
    p.setPen(QColor('white'))
    f = QFont()
    f.setPixelSize(max(8, int(size * 0.56)))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, (letter or '?')[0].upper())
    p.end()
    return QIcon(pm)


# ══════════════════════════════════════════════════════════════════════════════
# Design tokens — alignés sur le design system LIZPACK
# ══════════════════════════════════════════════════════════════════════════════

# Couleurs primaires (identiques au design system web)
_C_PRIMARY       = '#083D44'   # --color-primary
_C_PRIMARY_LIGHT = '#0a4a53'   # --color-primary-light
_C_PRIMARY_DARK  = '#062d32'   # --color-primary-dark
_C_SECONDARY     = '#2F7A3E'   # --color-secondary
_C_SECONDARY_LT  = '#256231'   # --color-secondary-light
_C_SECONDARY_DK  = '#1F5229'   # --color-secondary-dark

# ← _C_BLUE supprimé : utiliser _C_INFO (#3B82F6) à la place

# Fond / surfaces
_C_BG     = '#F5F7FA'   # --bg-primary
_C_CARD   = '#FFFFFF'   # --bg-secondary
_C_BG_TER = '#F9FAFB'   # --bg-tertiary
_C_HOVER  = '#F3F4F6'   # --bg-hover

# Texte
_C_TEXT   = '#1a1a1a'   # --text-primary
_C_MUTED  = '#4B5563'   # --text-secondary
_C_FAINT  = '#5B6472'   # --text-tertiary

# Bordures
_C_BORDER = '#E5E7EB'   # --border-primary

# États
_C_SUCCESS    = '#047857'
_C_SUCCESS_BG = '#D1FAE5'
_C_SUCCESS_TX = '#065F46'
_C_ERROR      = '#B91C1C'
_C_ERROR_BG   = '#FEE2E2'
_C_ERROR_TX   = '#991B1B'
_C_WARN       = '#B45309'
_C_WARN_BG    = '#FEF3C7'
_C_WARN_TX    = '#92400E'
_C_INFO       = '#1D4ED8'
_C_INFO_BG    = '#DBEAFE'
_C_INFO_TX    = '#1E40AF'

# Boutons : une seule famille, celle de la charte (espace client, Field).
# Principal vert, secondaire blanc a filet gris et texte petrole ; aucun
# fond teinte au survol ; desactive estompe (vert a 55 %).
_C_DESACTIVE = '#8DB695'
_BTN_PRIMARY = f"""
QPushButton {{
    background: {_C_SECONDARY}; color: white;
    border-radius: 10px; padding: 9px 20px;
    font-size: 14px; font-weight: 600; border: none;
}}
QPushButton:hover    {{ background: {_C_SECONDARY_LT}; }}
QPushButton:pressed  {{ background: {_C_SECONDARY_LT}; }}
QPushButton:focus    {{ border: 2px solid {_C_SECONDARY_DK}; }}
QPushButton:disabled {{ background: {_C_DESACTIVE}; color: white; }}
"""

_BTN_SUCCESS = _BTN_PRIMARY

_BTN_GHOST = f"""
QPushButton {{
    background: {_C_CARD}; color: {_C_PRIMARY};
    border-radius: 10px; padding: 8px 16px;
    font-size: 14px; font-weight: 600;
    border: 1px solid {_C_BORDER};
}}
QPushButton:hover    {{ border-color: #7C8595; }}
QPushButton:focus    {{ border: 2px solid {_C_PRIMARY}; }}
QPushButton:disabled {{ color: #9AA3AE; border-color: {_C_BORDER}; }}
"""

_BTN_ICON = f"""
QPushButton {{
    background: {_C_CARD}; color: {_C_PRIMARY};
    border-radius: 8px; padding: 6px;
    border: 1px solid {_C_BORDER};
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
}}
QPushButton:hover   {{ border-color: #7C8595; }}
QPushButton:focus   {{ border: 2px solid {_C_PRIMARY}; }}
"""

_QSS = f"""
QDialog {{
    background: {_C_BG};
    font-family: "Segoe UI", "Urbanist", Arial, sans-serif;
}}

/* ── Tabs ─────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {_C_BORDER};
    background: {_C_BG};
    top: -1px;
}}
/* Onglets de la charte : texte gris, actif vert souligne de vert, aucune
   teinte au survol. */
QTabBar::tab {{
    background: transparent;
    color: {_C_MUTED};
    padding: 10px 14px;
    border: none;
    border-bottom: 3px solid transparent;
    margin-right: 4px;
    font-size: 14px;
    font-weight: 600;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    color: {_C_SECONDARY};
    border-bottom: 3px solid {_C_SECONDARY};
}}
QTabBar::tab:focus {{
    color: {_C_SECONDARY};
}}

/* ── Cards / GroupBox ─────────────────────────────────────── */
QGroupBox {{
    background: {_C_CARD};
    border: 1px solid {_C_BORDER};
    border-radius: 12px;
    margin-top: 18px;
    padding: 18px 16px 14px 16px;
    font-weight: 700;
    font-size: 13px;
    color: {_C_PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: -1px;
    padding: 2px 8px;
    background: {_C_CARD};
    color: {_C_PRIMARY};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    border-radius: 4px;
    border: 1px solid {_C_BORDER};
}}

/* ── Inputs ───────────────────────────────────────────────── */
QLineEdit {{
    border: 1.5px solid {_C_BORDER};
    border-radius: 8px;
    padding: 9px 12px;
    background: {_C_CARD};
    color: {_C_TEXT};
    font-size: 14px;
    selection-background-color: {_C_PRIMARY};
    selection-color: white;
}}
QLineEdit:focus    {{ border-color: {_C_PRIMARY}; }}
QLineEdit:disabled {{ background: {_C_BG_TER}; color: {_C_FAINT}; border-color: {_C_BORDER}; }}

QComboBox {{
    border: 1.5px solid {_C_BORDER};
    border-radius: 8px;
    padding: 9px 36px 9px 12px;
    background: {_C_CARD};
    color: {_C_TEXT};
    font-size: 14px;
    min-height: 20px;
}}
QComboBox:focus    {{ border-color: {_C_PRIMARY}; }}
QComboBox:disabled {{ background: {_C_BG_TER}; color: {_C_MUTED}; }}
/* Liste figée (serveur choisi pendant la session) : sans flèche, elle se lit
   comme un champ en lecture, pas comme un bouton cassé. */
QComboBox::drop-down:disabled {{ width: 0px; border: none; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid {_C_BORDER};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: {_C_BG_TER};
}}
QComboBox::drop-down:hover {{ background: {_C_BORDER}; }}
/* Styler ::drop-down supprime la fleche native de Qt : sans regle
   ::down-arrow le bouton n'est qu'un rectangle gris et rien ne signale
   qu'il y a une liste. La regle est injectee ici. */
{_QSS_FLECHE}
/* La liste est une fenetre a part, posee dans un conteneur qui dessine
   deja son cadre. Lui en donner un second empilait deux bordures — l'une
   carree, l'autre arrondie — avec une marge visible entre les deux. */
QComboBox QAbstractItemView {{
    border: none;
    background: {_C_CARD};
    padding: 4px;
    outline: none;
}}
/* Sans regle ::item, Qt peint lui-meme la ligne courante en cadre blanc.
   Ces trois regles ne prennent effet qu'avec une vue Qt (voir setView). */
QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 5px 10px;
    border-radius: 6px;
    color: {_C_TEXT};
    border: none;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {_C_BG_TER};
    color: {_C_TEXT};
}}
QComboBox QAbstractItemView::item:selected {{
    background: {_C_SUCCESS_BG};
    color: {_C_SUCCESS_TX};
}}

/* ── Tree ─────────────────────────────────────────────────── */
QTreeWidget {{
    border: 1px solid {_C_BORDER};
    border-radius: 8px;
    background: {_C_CARD};
    alternate-background-color: {_C_BG_TER};
    outline: none;
    font-size: 13px;
    color: {_C_TEXT};
}}
QTreeWidget::item {{
    padding: 6px 6px;
    border-bottom: 1px solid {_C_BG};
}}
QTreeWidget::item:selected {{
    background: {_C_SUCCESS_BG};
    color: {_C_SUCCESS_TX};
    border-radius: 4px;
}}
QTreeWidget::item:hover:!selected {{
    background: {_C_HOVER};
}}
QHeaderView::section {{
    background: {_C_BG_TER};
    color: {_C_MUTED};
    border: none;
    border-bottom: 1.5px solid {_C_BORDER};
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ── Progress ─────────────────────────────────────────────── */
QProgressBar {{
    border: 1px solid {_C_BORDER};
    border-radius: 6px;
    background: {_C_BG_TER};
    height: 8px;
    color: transparent;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {_C_SECONDARY}, stop:1 {_C_PRIMARY});
    border-radius: 6px;
}}

/* ── Scrollbar ────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {_C_BG_TER}; width: 8px; border-radius: 4px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {_C_BORDER}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {_C_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {_C_BG_TER}; height: 8px; border-radius: 4px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {_C_BORDER}; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {_C_FAINT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""

# File-type → (icon_name, color)
# Taille d'ouverture par defaut, bornee a l'ecran disponible au lancement.
_GEOMETRIE_DEFAUT = (900, 880)
_SUPPORT_URL = 'https://lizpack.com/client/aide-support'
_GEOMETRIE_CLE    = 'LizpackPublisher/geometrie'

# Repartition des trois sections de l'onglet PostGIS, retenue d'une
# session a l'autre.
_SECTIONS_PG_CLE = 'LizpackPublisher/sections_postgis'
_AUTHCFG_BD_CLE  = 'LizpackPublisher/authcfg_bd'

# Le journal est-il replie ? Replie par defaut, et retenu d'une session
# a l'autre des que l'utilisateur en decide autrement.

# Fils encore en cours quand la fenetre se ferme. Ils survivent ici,
# hors de la fenetre, jusqu'a la fin de leur travail : les detruire
# avec elle ferait abandonner le processus QGIS.
_FILS_ORPHELINS = []

# Repertoire de travail : le dernier dossier que l'utilisateur a choisi,
# quel que soit l'endroit ou il l'a choisi. Toutes les boites de fichiers
# s'y ouvrent ensuite, au lieu de repartir chacune du dernier dossier
# retenu par Qt, qui pouvait etre celui d'un autre logiciel.
_REPERTOIRE_CLE = 'LizpackPublisher/repertoire_travail'

# Identifiants memorises. L'email et le drapeau vont dans QSettings ;
# le mot de passe, lui, ne va QUE dans le magasin d'authentification de
# QGIS, qui le chiffre derriere le mot de passe principal. L'ecrire dans
# QSettings le deposerait en clair dans QGIS3.ini.
_SOUVENIR_CLE = 'LizpackPublisher/se_souvenir'
_EMAIL_CLE    = 'LizpackPublisher/email'
_AUTHCFG_CLE  = 'LizpackPublisher/authcfg'

# Serveur de son organisation (édition entreprise) : adresse du portail et
# certificat d'autorité en clair (rien de secret) ; le jeton d'API, comme le
# mot de passe, seulement dans le magasin d'authentification de QGIS.
_MODE_CLE          = 'LizpackPublisher/serveur'
_PORTAIL_CLE       = 'LizpackPublisher/portail'
_CERTIFICAT_CLE    = 'LizpackPublisher/certificat'
_AUTHCFG_JETON_CLE = 'LizpackPublisher/authcfg_jeton'
_MSG_JETON_LECTURE = (tr("Jeton d'API en lecture seule : rien ne peut être envoyé, "
                      'déplacé ni supprimé. Créez un jeton sans lecture seule '
                      'dans le portail pour publier.'))

# Tables techniques de QGIS, jamais pertinentes comme couche pour l'utilisateur.
_PG_TABLES_INTERNES = {'layer_styles', 'qgis_projects'}

_FILE_ICONS = {
    '.qgz':     ('map',       _C_PRIMARY),
    '.qgs':     ('map',       _C_PRIMARY),
    '.qdash':   ('activity',   _C_PRIMARY),
    '.gpkg':    ('database',  '#8e44ad'),
    '.shp':     ('layers',    _C_SECONDARY),
    '.geojson': ('layers',    _C_SECONDARY),
    '.tif':     ('image',     '#d35400'),
    '.tiff':    ('image',     '#d35400'),
    '.png':     ('image',     '#d35400'),
    '.jpg':     ('image',     '#d35400'),
    '.pdf':     ('file-text', _C_ERROR),
    '.zip':     ('archive',   _C_MUTED),
}


# ══════════════════════════════════════════════════════════════════════════════
# Dialog
# ══════════════════════════════════════════════════════════════════════════════

class LizpackDialog(QDialog):

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface   = iface
        self.session = LizpackSession()
        self._open_project_api_path = None
        self._current_path  = '/'
        self._path_history  = []   # pile de navigation (Back)
        self._busy_count    = 0
        self._spinner_chars = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')
        self._spinner_idx   = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(100)
        self._spinner_timer.timeout.connect(self._tick_spinner)
        self._registered_pg_conn = None
        self._fils = []   # fils en cours, gardes en vie (voir _suivre)
        self._lecture_seule = False   # espace partage sans droit d'ecriture
        self._jeton_lecture = False   # jeton d'API en lecture seule (entreprise)
        self._dest_choisie = False    # destination fixee d'un clic

        self.setWindowTitle('LIZPACK Publisher')
        self.setMinimumSize(700, 720)  # les cinq onglets visibles sans flèches
        self.setWindowFlags(Qt.WindowType.Window)
        self.setStyleSheet(_QSS)
        self._build_ui()
        self._restaurer_geometrie()
        self._charger_identifiants()
        self._on_qgis_project_changed()   # etiquette + bouton Publier
        self._refresh_auth_state()
        # Détecter les changements de projet dans QGIS
        QgsProject.instance().readProject.connect(self._on_qgis_project_changed)
        # readProject ne se declenche qu'a l'ouverture : sans ces deux
        # signaux, fermer un projet ou l'enregistrer sous un autre nom
        # laissait l'etiquette et le bouton sur l'ancien etat.
        QgsProject.instance().cleared.connect(self._on_qgis_project_changed)
        QgsProject.instance().fileNameChanged.connect(self._on_qgis_project_changed)

        # Un clic ailleurs referme le journal. Les enfants consomment leurs
        # clics avant que la fenetre ne les voie : il faut donc ecouter au
        # niveau de l'application, et se desinscrire a la fermeture — un
        # filtre laisse derriere soi survit a la fenetre et fait tomber QGIS.
        QApplication.instance().installEventFilter(self)

    # ══════════════════════════════════════════════════════════════════
    # Repertoire de travail
    # ══════════════════════════════════════════════════════════════════

    def _repertoire_travail(self):
        """Dossier ou s'ouvrent toutes les boites de fichiers du plugin."""
        dossier = QSettings().value(_REPERTOIRE_CLE, '') or ''
        if dossier and os.path.isdir(dossier):
            return dossier
        return os.path.join(tempfile.gettempdir(), 'lizpack')

    def _definir_repertoire_travail(self, dossier):
        """Fait du dossier choisi le repertoire de travail.

        Il devient le point de depart des boites de fichiers suivantes et
        le « repertoire du projet » de QGIS, celui que l'explorateur
        affiche et auquel les chemins relatifs se rapportent.
        """
        if not dossier:
            return
        if not os.path.isdir(dossier):
            dossier = os.path.dirname(dossier)
        if not os.path.isdir(dossier):
            return

        if dossier == self._repertoire_travail():
            return
        QSettings().setValue(_REPERTOIRE_CLE, dossier)
        try:
            QgsProject.instance().setPresetHomePath(dossier)
        except Exception as e:
            # QGIS trop ancien : le reste fonctionne quand meme.
            journal.ignorer(e, 'répertoire de projet QGIS')
        self._log(tr('Répertoire de travail : {0}', dossier))

    # ══════════════════════════════════════════════════════════════════
    # Fils d'execution
    # ══════════════════════════════════════════════════════════════════

    def _suivre(self, fil):
        """Garde une reference sur un fil tant qu'il tourne.

        Chaque operation ecrase son attribut (self._list_worker et les
        autres). Si le fil precedent tournait encore, sa derniere
        reference Python disparaissait, l'objet etait collecte, et Qt
        abandonnait le processus sur
        « QThread: Destroyed while thread is still running » — QGIS se
        fermait instantanement, sans trace ni boite d'erreur.

        On purge au passage ceux qui ont fini : la liste ne grossit pas.
        """
        self._fils = [f for f in self._fils if f.isRunning()]
        self._fils.append(fil)
        return fil

    def _orpheliner_fils(self):
        """Detache les fils encore actifs avant que la fenetre disparaisse.

        Leurs signaux pointent vers cette fenetre ; les laisser branches
        ferait appeler des methodes d'un objet detruit. On les debranche
        et on confie les fils au module, qui les gardera en vie jusqu'au
        bout plutot que de bloquer l'interface en les attendant.
        """
        _FILS_ORPHELINS[:] = [f for f in _FILS_ORPHELINS if f.isRunning()]
        for fil in self._fils:
            if not fil.isRunning():
                continue
            for nom in ('finished', 'error', 'status', 'progress'):
                signal = getattr(fil, nom, None)
                if signal is None:
                    continue
                try:
                    signal.disconnect()
                except TypeError:
                    pass   # rien n'etait branche
            _FILS_ORPHELINS.append(fil)
        self._fils = []

    # ══════════════════════════════════════════════════════════════════
    # Identifiants memorises
    # ══════════════════════════════════════════════════════════════════

    def _charger_identifiants(self):
        """Pre-remplit le formulaire si l'utilisateur l'a demande.

        L'email vient de QSettings, le mot de passe du magasin
        d'authentification de QGIS. Si ce dernier est verrouille et que
        l'utilisateur refuse de saisir le mot de passe principal, on laisse
        simplement le champ vide : l'email pre-rempli reste utile.
        """
        reglages = QSettings()
        # Serveur choisi la derniere fois, et son adresse : rien de secret.
        if reglages.value(_MODE_CLE, '') == 'entreprise':
            self.cmb_serveur.setCurrentIndex(1)
        self.txt_portail.setText(reglages.value(_PORTAIL_CLE, '') or '')
        self.txt_certificat.setText(reglages.value(_CERTIFICAT_CLE, '') or '')
        if reglages.value(_SOUVENIR_CLE, False, type=bool) is not True:
            return
        jeton = reglages.value(_AUTHCFG_JETON_CLE, '') or ''
        if jeton:
            try:
                config = QgsAuthMethodConfig()
                if QgsApplication.authManager().loadAuthenticationConfig(jeton, config, True):
                    self.txt_jeton.setText(config.config('password', ''))
            except Exception as e:
                journal.ignorer(e, "lecture du jeton dans le magasin d'authentification")

        self.chk_souvenir.blockSignals(True)
        self.chk_souvenir.setChecked(True)
        self.chk_souvenir.blockSignals(False)
        self.txt_email.setText(reglages.value(_EMAIL_CLE, '') or '')

        authcfg = reglages.value(_AUTHCFG_CLE, '') or ''
        if not authcfg:
            return
        try:
            gestionnaire = QgsApplication.authManager()
            config = QgsAuthMethodConfig()
            if gestionnaire.loadAuthenticationConfig(authcfg, config, True):
                self.txt_pwd.setText(config.config('password', ''))
        except Exception as e:
            # Magasin verrouille ou configuration disparue : sans gravite,
            # l'utilisateur retape son mot de passe.
            journal.ignorer(e, 'lecture du magasin d\'authentification')

    def _enregistrer_identifiants(self, email, mot_de_passe, cle=_AUTHCFG_CLE,
                                  enregistrer_email=True):
        """Retient les identifiants apres une authentification reussie.

        Serveur de son organisation : `email` est l'adresse du portail et
        `mot_de_passe` le jeton d'API, garde sous sa propre cle."""
        reglages = QSettings()
        reglages.setValue(_SOUVENIR_CLE, True)
        if enregistrer_email:
            reglages.setValue(_EMAIL_CLE, email)

        try:
            gestionnaire = QgsApplication.authManager()
            config = QgsAuthMethodConfig()
            config.setName('LizPack Publisher')
            config.setMethod('Basic')
            config.setConfig('username', email)
            config.setConfig('password', mot_de_passe)

            ancien = reglages.value(cle, '') or ''
            if ancien:
                gestionnaire.removeAuthenticationConfig(ancien)

            if gestionnaire.storeAuthenticationConfig(config):
                reglages.setValue(cle, config.id())
                self._log(tr('Identifiants enregistrés (magasin QGIS).'), 'ok')
                return
        except Exception as e:
            self._log(tr('Mot de passe non enregistré : {0}', e), 'warn')

        # Repli : on garde l'email, jamais le mot de passe en clair.
        reglages.remove(cle)
        self._log(
            tr("Seul l'email a été retenu : le magasin d'authentification de QGIS n'est pas disponible."),
            'warn',
        )

    def _oublier_identifiants(self):
        """Efface tout ce qui a été retenu, mot de passe et jeton compris."""
        reglages = QSettings()
        for cle in (_AUTHCFG_CLE, _AUTHCFG_JETON_CLE):
            self._oublier_authcfg(reglages, cle)
        reglages.remove(_EMAIL_CLE)
        reglages.setValue(_SOUVENIR_CLE, False)

    def _oublier_authcfg(self, reglages, cle):
        authcfg = reglages.value(cle, '') or ''
        if authcfg:
            # Taire un echec ici laisserait croire le mot de passe efface
            # alors qu'il reste dans le magasin. removeAuthenticationConfig
            # renvoie False sans rien lever : on verifie donc que la
            # configuration a bien disparu, au lieu de se fier a l'absence
            # d'exception.
            reste = authcfg
            try:
                gestionnaire = QgsApplication.authManager()
                gestionnaire.removeAuthenticationConfig(authcfg)
                reste = authcfg if authcfg in gestionnaire.configIds() else ''
            except Exception as e:
                reste = "{} ({})".format(authcfg, e)
            if reste:
                self._log(
                    tr("Le mot de passe n'a pas pu etre retire du magasin "
                    "d'authentification de QGIS ({}). "
                    "Retirez-le depuis Preferences > Authentification.").format(reste),
                    'warn',
                )
        reglages.remove(cle)

    def _on_souvenir_change(self, coche):
        """Decocher efface immediatement, sans attendre la prochaine connexion."""
        if not coche:
            self._oublier_identifiants()
            self._log(tr('Identifiants oubliés.'))

    # ══════════════════════════════════════════════════════════════════
    # Geometrie de la fenetre
    # ══════════════════════════════════════════════════════════════════

    def _restaurer_geometrie(self):
        """Ouvre la fenetre a une taille utilisable.

        Sans cela elle s'ouvrait a son minimum : la console et l'arbre des
        fichiers etaient tasses des le premier lancement. On reprend la
        taille laissee par l'utilisateur si elle tient encore a l'ecran
        (un portable branche puis debranche d'un grand moniteur ferait
        sinon apparaitre la fenetre hors champ), sinon un defaut large,
        borne a 90 % de l'ecran pour rester valable sur un petit portable.
        """
        ecran = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        dispo = ecran.availableGeometry()

        sauve = QSettings().value(_GEOMETRIE_CLE)
        if isinstance(sauve, QByteArray) and not sauve.isEmpty():
            if self.restoreGeometry(sauve) and self._geometrie_atteignable():
                return

        largeur = min(_GEOMETRIE_DEFAUT[0], int(dispo.width()  * 0.9))
        hauteur = min(_GEOMETRIE_DEFAUT[1], int(dispo.height() * 0.9))
        self.resize(largeur, hauteur)
        # Centrer d'apres la taille visee, pas d'apres self.rect() : avant
        # le premier affichage celui-ci vaut encore la taille demandee par
        # le layout, et la fenetre partait hors ecran.
        self.move(
            dispo.x() + max(0, (dispo.width()  - largeur) // 2),
            dispo.y() + max(0, (dispo.height() - hauteur) // 2),
        )

    def _geometrie_atteignable(self):
        """La fenetre restauree est-elle encore accessible a la souris ?

        On verifie que son centre tombe sur un ecran branche. Exiger
        qu'elle soit entierement contenue serait trop strict : une fenetre
        collee au bord haut a son cadre qui deborde de la zone disponible
        et serait rejetee a tort. Un ecran debranche, lui, laisse le centre
        dans le vide et declenche bien le retour au defaut.
        """
        centre = self.frameGeometry().center()
        return any(
            e.availableGeometry().contains(centre) for e in QApplication.screens()
        )

    def detacher_de_qgis(self):
        """Coupe les liens avec QGIS avant que la fenetre soit detruite."""
        projet = QgsProject.instance()
        for signal in (projet.readProject, projet.cleared, projet.fileNameChanged):
            try:
                signal.disconnect(self._on_qgis_project_changed)
            except (TypeError, RuntimeError):
                pass   # deja debranche

    def _suivre_changement_ecran(self):
        """Refait la mise en page quand la fenetre change d'ecran.

        Sur un poste a plusieurs ecrans d'echelles differentes — ici un 150 %
        a cote de deux 100 % — Qt ne recalcule pas toujours la disposition
        au passage de l'un a l'autre : le cadre prend la taille demandee,
        le contenu reste dispose pour l'ancienne echelle, et la fenetre
        parait n'occuper que les deux tiers de sa largeur.

        Rien ne garantit la presence d'une fenetre native ni du signal :
        l'absence n'est pas une erreur, elle prive seulement du correctif.
        """
        try:
            poignee = self.windowHandle()
            if poignee is None:
                return
            poignee.screenChanged.connect(lambda _e: self._reposer_disposition())
        except Exception as e:
            journal.ignorer(e, "suivi du changement d'ecran")

    def _reposer_disposition(self):
        """Force Qt a refaire la mise en page a la taille courante."""
        try:
            disposition = self.layout()
            if disposition is None:
                return
            disposition.invalidate()
            disposition.activate()
            self.updateGeometry()
            # Une taille identique ne declenche pas de resizeEvent : on
            # passe par un pixel de moins, puis on revient.
            taille = self.size()
            self.resize(taille.width() - 1, taille.height())
            self.resize(taille)
        except Exception as e:
            journal.ignorer(e, "remise en page apres changement d'ecran")

    def showEvent(self, event):
        """Repose le filtre a chaque affichage.

        closeEvent le retire ; sans cela, la fenetre rouverte ne refermait
        plus le journal au clic.
        """
        QApplication.instance().installEventFilter(self)
        # La fenetre native n'existe qu'a partir de l'affichage : c'est le
        # premier moment ou l'on peut ecouter ses changements d'ecran.
        self._suivre_changement_ecran()
        super().showEvent(event)

    def _changer_langue(self, code):
        """Retient la langue choisie et rouvre l'extension dans cette langue.

        Les textes sont poses a la construction des fenetres : la seule facon
        sure de tout changer est de recharger l'extension, puis de la rouvrir.
        """
        from . import i18n
        if code == i18n.LANGUE:
            return
        if self.session.is_connected() or self._fils_actifs():
            rep = QMessageBox.question(
                self, tr('Langue'),
                tr("Changer de langue rouvre la fenêtre : la connexion en cours "
                   "et les opérations en cours seront interrompues. Continuer ?"))
            if rep != QMessageBox.StandardButton.Yes:
                return
        QSettings().setValue(i18n.CLE_LANGUE, code)
        paquet = __package__

        def relancer():
            import qgis.utils
            qgis.utils.reloadPlugin(paquet)
            extension = qgis.utils.plugins.get(paquet)
            if extension is not None:
                extension.run()

        QTimer.singleShot(0, relancer)

    def _fils_actifs(self):
        """Une operation tourne-t-elle encore ?"""
        for nom, valeur in vars(self).items():
            if hasattr(valeur, 'isRunning'):
                try:
                    if valeur.isRunning():
                        return True
                except RuntimeError:
                    pass
        return False

    def closeEvent(self, event):
        """Retenir la geometrie et mettre les fils encore actifs a l'abri."""
        QSettings().setValue(_GEOMETRIE_CLE, self.saveGeometry())
        self._memoriser_sections_pg()
        self._orpheliner_fils()
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception as e:
            journal.ignorer(e, "retrait du filtre d'evenements")
        super().closeEvent(event)

    # ══════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 0)
        body.setSpacing(10)

        # Tabs
        self.tabs = QTabWidget()
        # Avec une feuille de style, Qt calcule mal la largeur d'un onglet
        # portant une icone et rogne le libelle (« Connexior »). On lui
        # interdit de couper le texte et de repartir la largeur.
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)
        # Qt calcule la largeur d'un onglet avec la police du widget, mais la
        # feuille de style le peint en 14 px et en gras quand il est actif :
        # le libelle debordait (« Connexior »). On aligne la police du widget
        # sur celle qui sera reellement peinte, sinon le calcul est faux.
        _police = self.tabs.tabBar().font()
        _police.setBold(True)
        _police.setPixelSize(14)
        self.tabs.tabBar().setFont(_police)
        self.tabs.setIconSize(QSize(15, 15))

        t_conn = self._tab_connexion()
        t_proj = self._tab_projets()
        t_upld = self._tab_upload()
        t_pg   = self._tab_postgis()
        t_docs = self._tab_docs()

        self.tabs.addTab(t_conn, _icon('lock',         _C_PRIMARY, 15), '  ' + tr('Connexion'))
        self.tabs.addTab(t_proj, _icon('layers',       _C_PRIMARY, 15), '  ' + tr('Projets'))
        self.tabs.addTab(t_upld, _icon('upload-cloud', _C_PRIMARY, 15), '  ' + tr('Upload'))
        self.tabs.addTab(t_pg,   _icon('database',     _C_PRIMARY, 15), '  PostGIS')
        self.tabs.addTab(t_docs, _icon('book-open',    _C_PRIMARY, 15), '  ' + tr('Aide'))
        # Facteur 1 : l'espace disponible va aux onglets. Sans lui, Qt le
        # partage avec le bloc du journal, dont la hauteur est plafonnee :
        # celui-ci ne grandit pas mais ecarte son en-tete de sa console,
        # laissant un grand vide au milieu de la fenetre.
        body.addWidget(self.tabs, 1)

        # Log console
        body.addWidget(self._build_console())
        root.addLayout(body)

        # ── Loader (barre + label, visible pendant les opérations) ──
        loader_row = QHBoxLayout()
        loader_row.setContentsMargins(14, 0, 14, 4)
        loader_row.setSpacing(8)
        self._loader_lbl = QLabel()
        self._loader_lbl.setStyleSheet(
            f'font-size: 12px; color: {_C_MUTED}; font-family: monospace;'
        )
        self._loader_lbl.setVisible(False)
        loader_row.addWidget(self._loader_lbl)
        loader_row.addStretch()
        root.addLayout(loader_row)

        self._loader_bar = QProgressBar()
        self._loader_bar.setRange(0, 0)       # mode indéterminé
        self._loader_bar.setFixedHeight(3)
        self._loader_bar.setTextVisible(False)
        self._loader_bar.setVisible(False)
        self._loader_bar.setStyleSheet(
            f'QProgressBar {{ background: {_C_BORDER}; border: none; }}'
            f'QProgressBar::chunk {{ background: {_C_SECONDARY}; }}'
        )
        root.addWidget(self._loader_bar)

    def _build_header(self):
        hdr = QFrame()
        hdr.setObjectName('lp_header')
        hdr.setStyleSheet(f"""
            QFrame#lp_header {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {_C_PRIMARY_DARK}, stop:1 {_C_PRIMARY});
                border-bottom: 2px solid {_C_SECONDARY_DK};
                padding: 0;
            }}
            QFrame#lp_header QLabel {{
                background: transparent;
                color: white;
            }}
        """)
        h = QHBoxLayout(hdr)
        h.setContentsMargins(18, 13, 18, 13)
        h.setSpacing(0)

        # Map icon
        ico_lbl = QLabel()
        ico_lbl.setPixmap(_icon('map', 'white', 22).pixmap(22, 22))
        h.addWidget(ico_lbl)
        h.addSpacing(10)

        # Title + subtitle
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel('LIZPACK Publisher')
        lbl_title.setStyleSheet(
            'font-size: 14px; font-weight: 700; letter-spacing: 0.3px;'
        )
        lbl_sub = QLabel(tr('v{}').format(_version_du_plugin()))
        lbl_sub.setStyleSheet('font-size: 12px; color: rgba(255,255,255,.45);')
        titles.addWidget(lbl_title)
        titles.addWidget(lbl_sub)
        h.addLayout(titles)
        h.addStretch()

        # Langue de l'extension : changer rouvre la fenetre dans la nouvelle.
        from . import i18n
        # Un bouton et son menu : la liste deroulante heritait du texte blanc
        # de l'en-tete et s'ouvrait vide.
        self.cmb_langue = QPushButton(i18n.LANGUE.upper())
        self.cmb_langue.setAccessibleName(tr('Langue'))
        self.cmb_langue.setToolTip(tr('Langue'))
        self.cmb_langue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cmb_langue.setStyleSheet(
            'QPushButton { font-size: 13px; font-weight: 600; color: white; '
            'background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.35); '
            'border-radius: 8px; padding: 4px 12px; }'
            'QPushButton:focus { border: 2px solid white; }'
            'QPushButton::menu-indicator { width: 0px; }'
        )
        menu_langue = QMenu(self.cmb_langue)
        menu_langue.setStyleSheet(
            'QMenu { background: white; border: 1px solid #E5E7EB; padding: 4px; }'
            'QMenu::item { color: #111827; padding: 6px 18px; font-size: 13px; }'
            'QMenu::item:selected { color: #083D44; font-weight: 600; background: white; }'
        )
        for code, nom in (('fr', 'Français'), ('en', 'English'),
                          ('es', 'Español'), ('pt', 'Português')):
            act = menu_langue.addAction(f'{code.upper()}  {nom}')
            act.setCheckable(True)
            act.setChecked(code == i18n.LANGUE)
            act.triggered.connect(lambda _=False, c=code: self._changer_langue(c))
        self.cmb_langue.setMenu(menu_langue)
        h.addWidget(self.cmb_langue)
        h.addSpacing(8)

        # Status badge
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet(
            'font-size: 13px; font-weight: 500; '
            'color: rgba(255,255,255,.7); padding: 4px 10px; '
            'background: rgba(255,255,255,.08); border-radius: 20px;'
        )
        h.addWidget(self.lbl_status)
        return hdr

    def _build_console(self):
        """Le journal, avec un en-tete qui permet de le replier.

        Il occupait jusqu'a 180 pixels en permanence. Sur un portable, cela
        se prend sur la liste des fichiers, qui est le vrai sujet de la
        fenetre. On peut desormais le replier ; l'etat est retenu.
        """
        bloc = QWidget()
        pile = QVBoxLayout(bloc)
        pile.setContentsMargins(0, 0, 0, 0)
        pile.setSpacing(4)

        self.btn_journal = QPushButton()
        self.btn_journal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_journal.setStyleSheet(
            'QPushButton {'
            f'  color: {_C_MUTED}; background: transparent; border: none;'
            '   text-align: left; padding: 2px 4px; font-size: 12px;'
            '   font-weight: 600;'
            '}'
            f'QPushButton:hover {{ color: {_C_TEXT}; }}'
        )
        self.btn_journal.clicked.connect(self._basculer_journal)

        # L'en-tete tient sur une ligne : le titre repliable a gauche, la
        # copie a droite. Copier reste possible journal replie — c'est
        # justement ce qu'on fait pour envoyer une trace au support.
        self.btn_copier_journal = QPushButton(tr('Copier'))
        self.btn_copier_journal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copier_journal.setToolTip(
            tr('Copie tout le journal dans le presse-papiers.'))
        self.btn_copier_journal.setStyleSheet(
            'QPushButton {'
            f'  color: {_C_MUTED}; background: transparent; border: none;'
            '   padding: 2px 4px; font-size: 12px; font-weight: 600;'
            '}'
            f'QPushButton:hover {{ color: {_C_TEXT}; }}'
        )
        self.btn_copier_journal.clicked.connect(self._copier_journal)

        entete = QHBoxLayout()
        entete.setContentsMargins(0, 0, 0, 0)
        entete.addWidget(self.btn_journal)
        entete.addStretch()
        entete.addWidget(self.btn_copier_journal)
        pile.addLayout(entete)

        self.log = QTextEdit()
        self.log.setObjectName('lp_console')
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.setMaximumHeight(180)
        self.log.setStyleSheet(
            'QTextEdit#lp_console {'
            '  background: #1a1d24; color: #abb2bf;'
            '  border: 1px solid #2c3040;'
            '  border-radius: 8px;'
            '  font-family: "Consolas","Courier New",monospace;'
            '  font-size: 13px; padding: 8px; line-height: 1.5;'
            '}'
        )
        pile.addWidget(self.log)
        # Le bloc se contente de la hauteur de son contenu : sans cela il
        # recoit une part de l'espace libre et ecarte ses elements.
        bloc.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Maximum)

        # Toujours replie a l'ouverture : la place profite a la liste des
        # fichiers, et une erreur le deploie d'elle-meme. Le deploiement
        # ne vaut donc que pour la session en cours — retenir le choix
        # faisait qu'une seule consultation du journal l'ouvrait pour
        # toujours.
        self._appliquer_etat_journal(True)
        return bloc

    def _appliquer_etat_journal(self, replie):
        """Affiche ou masque le journal et met l'en-tete a jour."""
        self._journal_replie = replie
        self.log.setVisible(not replie)
        fleche = '▸' if replie else '▾'
        self.btn_journal.setText(tr('{0}  Journal', fleche))
        self.btn_journal.setToolTip(
            tr('Afficher le journal') if replie else tr('Replier le journal')
        )

    def eventFilter(self, objet, evenement):
        """Referme les panneaux de passage des qu'on clique ailleurs.

        Le journal et le rapport de validation se deploient sur un
        evenement — une erreur, un examen demande —, on les lit, puis ils
        encombrent. Les refermer d'un clic evite d'avoir a viser leur
        bouton.

        Rien n'est enregistre : la preference exprimee en cliquant sur
        l'en-tete du journal n'est pas ecrasee par un clic de travail.
        """
        if (evenement.type() != QEvent.Type.MouseButtonPress
                or not self.isVisible()):
            return super().eventFilter(objet, evenement)

        if (not getattr(self, '_journal_replie', True)
                and self._clic_hors_de(objet, (self.log, self.btn_journal,
                                               self.btn_copier_journal))):
            self._appliquer_etat_journal(True)

        return super().eventFilter(objet, evenement)

    def _clic_hors_de(self, objet, epargnes):
        """Vrai si le clic vise cette fenetre, hors des widgets epargnes.

        On epargne le panneau lui-meme — on y selectionne du texte, on y
        deplie des lignes — et la commande qui l'ouvre : refermer ce qu'on
        vient de demander serait deroutant.
        """
        if not isinstance(objet, QWidget):
            return False
        widget = objet
        dans_la_fenetre = False
        while widget is not None:
            if widget in epargnes:
                return False
            if widget is self:
                dans_la_fenetre = True
            widget = widget.parentWidget()
        return dans_la_fenetre

    def _copier_journal(self):
        """Met tout le journal dans le presse-papiers."""
        texte = self.log.toPlainText()
        if not texte.strip():
            self._log(tr('Le journal est vide.'), 'warn')
            return
        QApplication.clipboard().setText(texte)
        lignes = len(texte.strip().split(chr(10)))
        self._log(tr('Journal copié ({} ligne(s)).').format(lignes), 'ok')
        self._confirmer_copie()

    def _confirmer_copie(self):
        """Marque le bouton comme copie, puis le laisse revenir.

        Le journal est replie la plupart du temps : la ligne ajoutee dedans
        ne se voit pas. La confirmation doit donc etre sur le bouton, la ou
        le regard se trouve deja.
        """
        self.btn_copier_journal.setText(tr('✓  Copié'))
        self.btn_copier_journal.setStyleSheet(
            'QPushButton {'
            f'  color: {_C_SUCCESS_TX}; background: transparent; border: none;'
            '   padding: 2px 4px; font-size: 12px; font-weight: 600;'
            '}'
        )
        QTimer.singleShot(1600, self._retablir_bouton_copie)

    def _retablir_bouton_copie(self):
        """Remet le bouton dans son etat de repos.

        Appele par un minuteur : la fenetre peut avoir ete fermee entre
        temps, auquel cas le bouton n'existe plus cote Qt.
        """
        try:
            self.btn_copier_journal.setText(tr('Copier'))
            self.btn_copier_journal.setStyleSheet(
                'QPushButton {'
                f'  color: {_C_MUTED}; background: transparent; border: none;'
                '   padding: 2px 4px; font-size: 12px; font-weight: 600;'
                '}'
                f'QPushButton:hover {{ color: {_C_TEXT}; }}'
            )
        except RuntimeError as e:
            journal.ignorer(e, 'retablissement du bouton de copie')

    def _basculer_journal(self):
        """Replie ou deploie le journal, pour la session en cours."""
        self._appliquer_etat_journal(not getattr(self, '_journal_replie', False))

    # ── Onglet Aide / Documentation ──────────────────────────────────
    def _tab_docs(self):
        # NOTE accept : remplacer lizpack.com par accept.lizpack.com

        from qgis.PyQt.QtWidgets import QScrollArea

        tab         = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 16, 20, 20)
        v.setSpacing(12)

        # ── Helper : section titre ─────────────────────────────────────
        def _section_title(text, icon_name, color):
            row = QHBoxLayout()
            row.setSpacing(8)
            ico = QLabel()
            ico.setPixmap(_icon(icon_name, color, 18).pixmap(18, 18))
            ico.setFixedSize(18, 18)
            ico.setStyleSheet('background: transparent;')
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f'font-size: 13px; font-weight: 700; color: {color};'
                f'letter-spacing: 0.5px; text-transform: uppercase; background: transparent;'
            )
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f'color: {_C_BORDER};')
            row.addWidget(ico)
            row.addWidget(lbl)
            row.addWidget(sep, 1)
            w = QWidget()
            w.setLayout(row)
            return w

        # ── Helper : étape numérotée ───────────────────────────────────
        def _step(num, title, detail):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.setContentsMargins(0, 0, 0, 0)

            badge = QLabel(str(num))
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f'background: {_C_PRIMARY}; color: white; border-radius: 13px;'
                f'font-size: 13px; font-weight: 700;'
            )

            txt = QVBoxLayout()
            txt.setSpacing(1)
            t = QLabel(title)
            t.setStyleSheet(f'font-size: 13px; font-weight: 600; color: {_C_TEXT}; background: transparent;')
            d = QLabel(detail)
            d.setStyleSheet(f'font-size: 12px; color: {_C_MUTED}; background: transparent;')
            d.setWordWrap(True)
            txt.addWidget(t)
            txt.addWidget(d)

            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(txt, 1)
            w = QWidget()
            w.setContentsMargins(0, 0, 0, 0)
            w.setLayout(row)
            return w

        # ── Helper : tip coloré ────────────────────────────────────────
        def _tip(text, level='info'):
            colors = {
                'info':  (_C_INFO_BG,    _C_INFO_TX,    'help-circle'),
                'ok':    (_C_SUCCESS_BG, _C_SUCCESS_TX, 'check-circle'),
                'warn':  (_C_WARN_BG,    _C_WARN_TX,    'alert-circle'),
            }
            bg, fg, ico_name = colors.get(level, colors['info'])
            f = QFrame()
            f.setStyleSheet(
                f'QFrame {{ background: {bg}; border-radius: 8px; border: none; }}'
            )
            row = QHBoxLayout(f)
            row.setContentsMargins(12, 8, 12, 8)
            row.setSpacing(10)
            ico = QLabel()
            ico.setPixmap(_icon(ico_name, fg, 16).pixmap(16, 16))
            ico.setFixedSize(16, 16)
            ico.setStyleSheet('background: transparent;')
            lbl = QLabel(text)
            lbl.setStyleSheet(f'font-size: 12px; color: {fg}; background: transparent;')
            lbl.setWordWrap(True)
            row.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(lbl, 1)
            return f

        # ══════════════════════════════════════════════════════════════
        # SECTION 1 — Premiers pas
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title(tr('Premiers pas'), 'zap', _C_PRIMARY))
        v.addWidget(_step(1, tr('Se connecter'),
            tr('Dans l\'onglet Connexion, entrez votre email et mot de passe LIZPACK, '
            'puis cliquez sur Se connecter. Serveur LizPack de votre organisation : '
            'choisissez « Serveur de mon organisation », entrez l\'adresse du portail '
            'et un jeton d\'API (portail : Paramètres > Sécurité > Créer un jeton).')))
        v.addWidget(_step(2, tr('Choisir une instance'),
            tr('Sélectionnez votre instance dans la liste déroulante (statut RUNNING = active), '
            'puis cliquez sur Connecter à l\'instance.')))
        v.addWidget(_step(3, tr('Naviguer dans les fichiers'),
            tr('L\'onglet Projets affiche vos fichiers. Double-cliquez sur un dossier pour y entrer. '
            'Utilisez ← Retour pour remonter.')))
        v.addWidget(_step(4, tr('Retenir vos identifiants'),
            tr("Cochez Se souvenir de mes identifiants : le mot de passe est "
            "confié au magasin d'authentification de QGIS, qui le chiffre. "
            "Il n'est jamais écrit en clair.")))
        v.addWidget(_step(5, tr('Espaces partagés'),
            tr("Si une équipe vous a partagé ses instances, un choix Espace "
            "apparaît. Vos droits y sont ceux que le propriétaire vous a "
            "accordés.")))
        v.addWidget(_step(6, tr('Rafraîchir'),
            tr("Le bouton Rafraîchir redemande au serveur tout ce qui a été lu "
            "à la connexion : identifiants de la base, quota, permissions et "
            "fichiers. À employer après une modification faite depuis votre "
            "espace client, sans avoir à vous déconnecter.")))
        v.addWidget(_tip(
            tr('Vos identifiants sont ceux de votre espace client LIZPACK (lizpack.com).'),
            'info'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 2 — Ouvrir un projet
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title(tr('Ouvrir un projet depuis le serveur'), 'download', _C_PRIMARY))
        v.addWidget(_step(1, tr('Localiser le fichier .qgs ou .qgz'),
            tr('Naviguez dans l\'arborescence jusqu\'au fichier projet.')))
        v.addWidget(_step(2, tr('Double-cliquer ou cliquer Ouvrir'),
            tr('Le projet est téléchargé dans un dossier temporaire local avec toutes ses données '
            '(shapefiles, rasters, GeoJSON…). Le chemin reproduit la structure du serveur.')))
        v.addWidget(_step(3, tr('Choisir où enregistrer'),
            tr('Le plugin demande le dossier de destination, puis rapatrie le dossier serveur entier, sous-dossiers compris, en une seule requête. Ce dossier devient le répertoire de travail.')))
        v.addWidget(_step(4, tr('QGIS charge le projet'),
            tr('Les couches sont disponibles immédiatement. Si des fichiers manquent sur le serveur, '
            'un avertissement s\'affiche dans la console.')))
        v.addWidget(_step(5, tr('Les couches PostGIS se rebranchent seules'),
            tr("Un projet publié porte l'adresse interne de la base, celle que "
            "Lizmap emploie depuis le serveur. À l'ouverture, le plugin la "
            "remplace par celle de votre poste et confie le mot de passe au "
            "magasin d'authentification de QGIS. Sans cela, les couches "
            "arrivaient vides.")))
        v.addWidget(_tip(
            tr("Le mot de passe de la base n'est jamais écrit en clair dans le "
            "projet enregistré sur votre disque : celui-ci ne porte qu'une "
            "référence au magasin de QGIS."), 'ok'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 3 — Publier un projet
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title(tr('Publier un projet vers Lizmap'), 'upload-cloud', _C_PRIMARY))
        v.addWidget(_step(1, tr('Ouvrir ou créer un projet dans QGIS'),
            tr("Tout projet ouvert dans QGIS peut être publié, qu'il vienne du serveur ou d'un fichier local.")))
        v.addWidget(_step(2, tr('Définir la destination'),
            tr('Cliquez sur un fichier dans l\'arbre pour pré-remplir le chemin de destination, '
            'ou saisissez-le manuellement (ex: /qgis/mon-projet.qgs).')))
        v.addWidget(_step(3, tr('Cliquer sur Publier vers Lizmap'),
            tr('Le projet est sauvegardé localement puis uploadé sur le serveur. '
            'Lizmap recharge automatiquement la configuration.')))
        v.addWidget(_tip(
            tr('Après publication, vérifiez que votre fichier lizmap_plugin_print.qgs (si existant) '
            'est aussi à jour sur le serveur.'), 'warn'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 3 bis — Valider un projet
        # ══════════════════════════════════════════════════════════════
        v.addSpacing(6)
        v.addWidget(_section_title(tr('Valider un projet'), 'check-circle', _C_PRIMARY))
        v.addWidget(_step(1, tr('Avant de publier'),
            tr("Le bouton Valider le projet fait examiner le projet actif par le "
            "serveur, sans rien publier ni écrire. Un clic droit sur un projet "
            "de la liste examine celui qui est déjà en ligne.")))
        v.addWidget(_step(2, tr('Ce qui est contrôlé'),
            tr("Connexions de la base, clefs primaires, index spatiaux, "
            "projections, cohérence entre le système déclaré et celui de la "
            "base, expressions et chemins locaux.")))
        v.addWidget(_step(3, tr('Lire le rapport'),
            tr("Les signalements sont classés par gravité. Choisissez une ligne "
            "pour lire la conséquence et la solution.")))
        v.addWidget(_tip(
            tr("Deux règles seules font refuser la publication : des couches en "
            "projections mélangées, et des connexions de base étrangères à "
            "l'instance. Les autres signalements dégradent la carte sans "
            "l'interdire."), 'warn'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 4 — Gestion des fichiers
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title(tr('Gestion des fichiers'), 'folder-plus', '#e67e22'))
        v.addWidget(_step(1, tr('Créer un dossier'),
            tr('Cliquez sur l\'icône 📁+ ou faites un clic droit → Nouveau dossier ici.')))
        v.addWidget(_step(2, tr('Uploader des fichiers'),
            tr('Cliquez sur l\'icône ↑ pour sélectionner un ou plusieurs fichiers locaux '
            'à envoyer dans le dossier courant.')))
        v.addWidget(_step(3, tr('Renommer / Supprimer'),
            tr('Sélectionnez un élément et cliquez sur les icônes ✏️ ou 🗑, '
            'ou utilisez le clic droit. La suppression demande confirmation.')))
        v.addWidget(_tip(
            tr('La sélection multiple (Ctrl+clic) permet de supprimer '
            "plusieurs éléments d'un coup."), 'info'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 5 — PostGIS
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title(tr('Connexion PostGIS'), 'database', '#8e44ad'))
        v.addWidget(_step(1, tr('Vérifier la disponibilité'),
            tr('L\'onglet PostGIS est disponible uniquement si votre instance dispose d\'une base '
            'PostgreSQL/PostGIS configurée.')))
        v.addWidget(_step(2, tr('Charger les tables'),
            tr('Cliquez sur Charger les tables pour lister les couches géométriques disponibles.')))
        v.addWidget(_step(3, tr('Ajouter une couche dans QGIS'),
            tr('Double-cliquez sur une table pour l\'ajouter directement en tant que couche vectorielle.')))
        v.addWidget(_tip(tr('Si PostGIS n\'est pas disponible, un bandeau jaune s\'affiche dans l\'onglet.'), 'warn'))

        # ══════════════════════════════════════════════════════════════
        v.addSpacing(6)
        v.addWidget(_section_title(tr('Santé de la base'), 'activity', _C_ERROR))
        v.addWidget(_step(1, tr('Diagnostiquer'),
            tr("Analyse la base sans rien y écrire : index spatiaux manquants, "
            "tables sans clef primaire utilisable, clefs en bigint que QGIS "
            "Serveur refuse, statistiques périmées, polygones trop détaillés.")))
        v.addWidget(_step(2, tr('Lire le tableau'),
            tr("La colonne Correction dit ce que le plugin peut faire : "
            "Automatique, Sur confirmation, ou À la main. Survolez une ligne "
            "pour voir le SQL et, s'il y a lieu, la commande pour défaire.")))
        v.addWidget(_step(3, tr('Optimiser'),
            tr("Tout optimiser n'applique que les corrections sans risque : index, statistiques. Celles qui touchent à la structure demandent d'être sélectionnées, et une confirmation détaille leur conséquence.")))
        v.addWidget(_step(4, tr('Exporter'),
            tr("Enregistrez le diagnostic en CSV pour le transmettre, ou en SQL "
            "pour le rejouer. Dans le script, les corrections à la main sont "
            "commentées.")))
        v.addWidget(_tip(
            tr("Un index et des statistiques se défont sans perte. Une colonne "
            "ajoutée ou un type converti modifient la table : le plugin ne les "
            "applique jamais sans votre accord explicite."), 'info'))

        # ══════════════════════════════════════════════════════════════
        v.addSpacing(6)
        v.addWidget(_section_title(tr('Le journal'), 'file-text', _C_MUTED))
        v.addWidget(_step(1, tr('Ouvrir et fermer'),
            tr("Le journal, en bas de la fenêtre, s'ouvre en cliquant sur son "
            "titre et se referme d'un clic n'importe où ailleurs. Il est "
            "toujours replié à l'ouverture du plugin.")))
        v.addWidget(_step(2, tr('Copier'),
            tr("Le bouton Copier place tout le journal dans le presse-papiers, même replié : c'est ce qu'il faut joindre à une demande au support.")))
        v.addWidget(_tip(
            tr("Une erreur déploie le journal d'elle-même : elle ne peut pas "
            "passer inaperçue."), 'info'))

        # ══════════════════════════════════════════════════════════════
        # Bouton support
        # ══════════════════════════════════════════════════════════════
        v.addSpacing(4)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f'color: {_C_BORDER};')
        v.addWidget(sep2)

        # Le support : celui de LizPack, ou celui de l'organisation quand on
        # est sur son portail (Paramètres > Apparence du portail).
        self._support_url = _SUPPORT_URL
        self.ligne_support = QWidget()
        support_row = QHBoxLayout(self.ligne_support)
        support_row.setContentsMargins(0, 0, 0, 0)
        lbl_support = QLabel(tr('Vous ne trouvez pas la réponse ?'))
        lbl_support.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; background: transparent;')
        self.btn_support = _btn(tr('Contacter le support'), 'message-circle', _C_PRIMARY, _BTN_GHOST)
        self.btn_support.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self._support_url))
        )
        support_row.addWidget(lbl_support)
        support_row.addStretch()
        support_row.addWidget(self.btn_support)
        v.addWidget(self.ligne_support)

        footer = QLabel('LIZPACK Publisher · Plugin QGIS · v{}'.format(
            _version_du_plugin()))
        footer.setStyleSheet(f'font-size: 12px; color: {_C_FAINT}; padding: 2px 0;')
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(footer)

        scroll_area.setWidget(inner)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)
        return tab

    # ── Onglet Connexion ─────────────────────────────────────────────
    def _tab_connexion(self):
        # Sous une certaine hauteur, Qt cesse de respecter la taille
        # minimale des champs et les ecrase : le texte d'un QLineEdit se
        # retrouve coupe en deux. Le contenu defile donc, comme dans
        # l'onglet PostGIS, plutot que d'etre comprime.
        from qgis.PyQt.QtWidgets import QScrollArea

        tab = QWidget()
        exterieur = QVBoxLayout(tab)
        exterieur.setContentsMargins(0, 0, 0, 0)
        exterieur.setSpacing(0)

        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.Shape.NoFrame)
        defilement.setStyleSheet(
            'QScrollArea { background: transparent; border: none; }')

        interieur = QWidget()
        v = QVBoxLayout(interieur)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        # ── Étape 1
        grp1 = QGroupBox(tr('Étape 1 · Identifiants'))
        # Une ligne par champ dans une pile : une ligne masquée (champs de
        # l'autre serveur) ne laisse pas de trou, à l'inverse de QFormLayout.
        f1   = _Lignes(grp1)

        # LizPack (lizpack.com) ou le serveur LizPack Entreprise installé
        # dans l'organisation : même plugin, autre porte d'entrée.
        self.cmb_serveur = _liste_deroulante(QComboBox())
        self.cmb_serveur.addItem(tr('LizPack (lizpack.com)'), userData='mutualise')
        self.cmb_serveur.addItem(tr('Serveur de mon organisation'), userData='entreprise')
        self.cmb_serveur.setAccessibleName(tr('Serveur'))
        f1.addRow(_form_label(tr('Serveur')), self.cmb_serveur)

        self.txt_email = _input_with_icon('votre@email.com')
        self.txt_pwd   = _input_with_icon('••••••••', password=True)
        self.txt_pwd.returnPressed.connect(self._do_login)
        self.lbl_email = _form_label(tr('Email'))
        self.lbl_pwd   = _form_label(tr('Mot de passe'))
        f1.addRow(self.lbl_email, self.txt_email)
        f1.addRow(self.lbl_pwd,   self.txt_pwd)

        self.txt_portail = _input_with_icon('https://portail.mon-organisation.org')
        self.txt_portail.setToolTip(
            tr("L'adresse du portail LizPack de votre organisation, telle "
            "que vous l'ouvrez dans le navigateur."))
        self.txt_jeton = _input_with_icon('lzp_…', password=True)
        self.txt_jeton.setToolTip(
            tr("À créer dans le portail : Paramètres > Sécurité > Créer un jeton "
            "(« Gérer les fichiers » au minimum). "
            'Il remplace le mot de passe et le code de double authentification.'))
        self.txt_jeton.returnPressed.connect(self._do_login)
        self.txt_certificat = _input_with_icon(tr('Facultatif : certificat .pem ou .crt'))
        self.txt_certificat.setToolTip(
            tr('Seulement si le portail utilise un certificat de votre organisation '
            "que le système ne reconnaît pas : le fichier de l'autorité de certification."))
        self.btn_certificat = QPushButton(tr('Parcourir…'))
        self.btn_certificat.setStyleSheet(_BTN_GHOST)
        self.btn_certificat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_certificat.setToolTip(tr('Choisir le fichier du certificat'))
        self.btn_certificat.clicked.connect(self._choisir_certificat)
        ligne_cert = QHBoxLayout()
        ligne_cert.setContentsMargins(0, 0, 0, 0)
        ligne_cert.addWidget(self.txt_certificat, 1)
        ligne_cert.addWidget(self.btn_certificat)
        self.zone_certificat = QWidget()
        self.zone_certificat.setLayout(ligne_cert)
        self.lbl_portail    = _form_label(tr('Portail'))
        self.lbl_jeton      = _form_label(tr("Jeton d'API"))
        self.lbl_certificat = _form_label(tr('Certificat'))
        f1.addRow(self.lbl_portail,    self.txt_portail)
        f1.addRow(self.lbl_jeton,      self.txt_jeton)
        f1.addRow(self.lbl_certificat, self.zone_certificat)
        self.cmb_serveur.currentIndexChanged.connect(lambda _i: self._sync_mode_serveur())

        self.chk_souvenir = QCheckBox(tr('Se souvenir de mes identifiants'))
        self.chk_souvenir.setToolTip(
            tr('Le mot de passe est confie au magasin d\'authentification de '
            'QGIS, qui le chiffre. QGIS demandera son mot de passe '
            'principal a la premiere utilisation.')
        )
        self.chk_souvenir.setStyleSheet(f'font-size: 12px; color: {_C_MUTED};')
        self.chk_souvenir.toggled.connect(self._on_souvenir_change)
        f1.addRow('', self.chk_souvenir)
        v.addWidget(grp1)
        self._sync_mode_serveur()

        row1 = QHBoxLayout()
        self.btn_login = _btn(tr('Se connecter'), 'lock', 'white', _BTN_PRIMARY)
        self.btn_logout = _btn(tr('Déconnexion'), 'log-out', _C_MUTED, _BTN_GHOST)
        self.btn_logout.setEnabled(False)
        self.btn_login.clicked.connect(self._do_login)
        self.btn_logout.clicked.connect(self._do_logout)
        row1.addWidget(self.btn_login)
        row1.addWidget(self.btn_logout)
        row1.addStretch()
        v.addLayout(row1)

        # ── Étape 2
        self.grp_instance = QGroupBox(tr('Étape 2 · Sélectionner une instance'))
        self.grp_instance.setEnabled(False)
        f2 = _Lignes(self.grp_instance)

        # Espace de travail : son propre compte, ou celui d'une equipe
        # qui nous a partage des instances. Masque tant qu'aucune equipe
        # n'existe, pour ne pas encombrer le cas courant.
        self.cmb_espace = _liste_deroulante(QComboBox())
        self.cmb_espace.setMinimumWidth(300)
        self.cmb_espace.currentIndexChanged.connect(self._on_espace_change)
        self.lbl_espace = _form_label(tr('Espace'))
        f2.addRow(self.lbl_espace, self.cmb_espace)
        self.lbl_espace.parentWidget().setVisible(False)

        self.cmb_instance = _liste_deroulante(QComboBox())
        self.cmb_instance.setMinimumWidth(300)
        f2.addRow(_form_label(tr('Instance')), self.cmb_instance)
        v.addWidget(self.grp_instance)

        row2 = QHBoxLayout()
        self.btn_connect = _btn(tr("Connecter à l'instance"), 'link', 'white', _BTN_SUCCESS)
        self.btn_connect.setEnabled(False)
        self.btn_connect.clicked.connect(self._do_connect_instance)
        self.cmb_instance.currentIndexChanged.connect(
            lambda _idx: self._sync_connect_button()
        )
        self.btn_rafraichir = _btn(tr('Rafraîchir'), 'refresh',
                                   _C_PRIMARY, _BTN_GHOST)
        self.btn_rafraichir.setEnabled(False)
        self.btn_rafraichir.setToolTip(
            tr('Redemande au serveur les informations de cette instance : '
            'identifiants de base, quota, permissions, fichiers.'))
        self.btn_rafraichir.clicked.connect(self._do_rafraichir_connexion)
        row2.addWidget(self.btn_connect)
        row2.addWidget(self.btn_rafraichir)
        row2.addStretch()
        v.addLayout(row2)

        self.lbl_instance_info = QLabel('')
        self.lbl_instance_info.setStyleSheet(
            f'color: {_C_SUCCESS_TX}; font-size: 13px; font-weight: 600; padding: 4px 2px;'
        )
        v.addWidget(self.lbl_instance_info)
        v.addStretch()

        defilement.setWidget(interieur)
        exterieur.addWidget(defilement)
        return tab

    # ── Onglet Projets ───────────────────────────────────────────────
    def _tab_projets(self):
        # Cet onglet a grossi : arbre, barre d'actions, publication, et
        # maintenant le rapport de validation. Sous une certaine hauteur,
        # Qt cesse de respecter les tailles minimales et empile les blocs
        # les uns sur les autres — boutons a cheval, arbre reduit a une
        # ligne. Le contenu defile donc, comme dans Connexion et PostGIS.
        from qgis.PyQt.QtWidgets import QScrollArea

        tab = QWidget()
        exterieur = QVBoxLayout(tab)
        exterieur.setContentsMargins(0, 0, 0, 0)
        exterieur.setSpacing(0)

        # Deux activites distinctes cohabitaient dans un seul onglet : gerer
        # des fichiers, et lire un rapport. Elles se disputaient la hauteur,
        # et le rapport chassait l'arbre. Chacune la sienne.
        self.sous_onglets = QTabWidget()
        # Meme piege que pour les onglets principaux : Qt calcule la largeur
        # d'un onglet avec la police du widget, alors que la feuille de style
        # le peint en 14 px et en gras. Le libelle debordait, rogne des deux
        # cotes (« tionnaire de fich »). On aligne la police sur celle qui
        # sera reellement peinte, et on interdit la coupe.
        self.sous_onglets.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.sous_onglets.tabBar().setExpanding(False)
        _police_sous = self.sous_onglets.tabBar().font()
        _police_sous.setBold(True)
        _police_sous.setPixelSize(14)
        self.sous_onglets.tabBar().setFont(_police_sous)
        exterieur.addWidget(self.sous_onglets)

        # ══ Sous-onglet 1 — Gestionnaire de fichiers ══════════════════
        page_fichiers = QWidget()
        pf = QVBoxLayout(page_fichiers)
        pf.setContentsMargins(0, 0, 0, 0)
        pf.setSpacing(0)

        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.Shape.NoFrame)
        defilement.setStyleSheet(
            'QScrollArea { background: transparent; border: none; }')

        interieur = QWidget()
        v = QVBoxLayout(interieur)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        # ── Barre de navigation ──────────────────────────────────────
        # Barre de navigation dans un widget : on la masque d'un bloc
        # quand l'espace n'ouvre pas les fichiers.
        self.barre_nav = QWidget()
        nav = QHBoxLayout(self.barre_nav)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(6)
        self.btn_back = QPushButton(tr('← Retour'))
        self.btn_back.setToolTip(tr('Remonter au dossier parent'))
        self.btn_back.setStyleSheet(f"""
QPushButton {{
    background: {_C_BG_TER};
    color: {_C_TEXT};
    border: 1.5px solid {_C_BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover   {{ background: {_C_HOVER}; border-color: {_C_PRIMARY}; color: {_C_PRIMARY}; }}
QPushButton:pressed {{ background: {_C_BORDER}; }}
QPushButton:disabled {{ color: {_C_FAINT}; border-color: {_C_BORDER}; background: {_C_BG_TER}; }}
        """)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._nav_back)
        self.lbl_path = QLabel('/')
        self.lbl_path.setStyleSheet(
            f'color: {_C_MUTED}; font-size: 13px; font-family: monospace;'
            f'padding: 4px 8px; background: {_C_BG_TER}; border-radius: 6px;'
        )
        self.lbl_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.lbl_path)
        v.addWidget(self.barre_nav)

        # Affiche a la place de l'arbre quand l'espace ne donne pas acces
        # aux fichiers. Le serveur refuse alors jusqu'au simple listage :
        # montrer un arbre vide laisserait croire a un dossier vide.
        self.fichiers_interdits = QFrame()
        self.fichiers_interdits.setObjectName('lp_bandeau_interdit')
        self.fichiers_interdits.setStyleSheet(
            f'QFrame#lp_bandeau_interdit {{ background: {_C_WARN_BG}; '
            f'border: 1px solid #FCD34D; border-radius: 8px; }}'
        )
        fi_h = QHBoxLayout(self.fichiers_interdits)
        fi_h.setContentsMargins(12, 10, 12, 10)
        fi_ico = QLabel()
        fi_ico.setPixmap(_icon('lock', _C_WARN, 16).pixmap(16, 16))
        fi_ico.setFixedSize(16, 16)
        fi_ico.setStyleSheet('background: transparent; border: none;')
        self.lbl_fichiers_interdits = QLabel('')
        self.lbl_fichiers_interdits.setWordWrap(True)
        self.lbl_fichiers_interdits.setStyleSheet(
            f'color: {_C_WARN_TX}; font-size: 13px; background: transparent; '
            'border: none;'
        )
        fi_h.addWidget(fi_ico, 0, Qt.AlignmentFlag.AlignTop)
        fi_h.addSpacing(8)
        fi_h.addWidget(self.lbl_fichiers_interdits, 1)
        self.fichiers_interdits.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum,
        )
        self.fichiers_interdits.setVisible(False)
        v.addWidget(self.fichiers_interdits)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Fichier'), tr('Taille'), tr('Modifié')])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # 80 px suffisaient a « 1.6 MB » ; « 12 elements » deborde.
        self.tree.header().resizeSection(1, 110)
        # 90 px suffisaient a la date seule ; avec l'heure, la colonne
        # tronquait.
        self.tree.header().resizeSection(2, 130)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_file_dblclick)
        self.tree.itemClicked.connect(self._on_file_click)
        self.tree.itemSelectionChanged.connect(self._sync_open_button)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        # Sans plancher, l'arbre etait le premier sacrifie quand le
        # rapport de validation s'ouvrait : il tombait a une ligne.
        self.tree.setMinimumHeight(200)
        v.addWidget(self.tree, 1)

        # Raccourcis clavier sur l'arbre
        from qgis.PyQt.QtWidgets import QShortcut
        from qgis.PyQt.QtGui import QKeySequence
        QShortcut(QKeySequence.StandardKey.Copy,  self.tree, self._do_copy)
        QShortcut(QKeySequence('Ctrl+X'), self.tree, self._do_cut)
        QShortcut(QKeySequence.StandardKey.Paste, self.tree, self._do_paste)
        QShortcut(QKeySequence.StandardKey.Delete, self.tree, self._do_delete_selected)

        # ── Barre d'actions fichiers ─────────────────────────────────
        self.barre_actions = QWidget()
        acts = QHBoxLayout(self.barre_actions)
        acts.setContentsMargins(0, 0, 0, 0)
        acts.setSpacing(4)

        self.btn_open = _btn(tr('Ouvrir'), 'download', 'white', _BTN_PRIMARY)
        self.btn_open.setToolTip(tr('Ouvrir le projet .qgs/.qgz sélectionné dans QGIS'))
        self.btn_open.clicked.connect(self._do_open_project)
        self.btn_open.setEnabled(False)

        self.btn_mkdir = QPushButton()
        self.btn_mkdir.setIcon(_icon('folder-plus', _C_MUTED, 15))
        self.btn_mkdir.setIconSize(QSize(15, 15))
        self.btn_mkdir.setToolTip(tr('Nouveau dossier'))
        self.btn_mkdir.setStyleSheet(_BTN_ICON)
        self.btn_mkdir.clicked.connect(self._do_create_folder)

        self.btn_upload_here = QPushButton()
        self.btn_upload_here.setIcon(_icon('upload', _C_MUTED, 15))
        self.btn_upload_here.setIconSize(QSize(15, 15))
        self.btn_upload_here.setToolTip(tr('Uploader des fichiers ici'))
        self.btn_upload_here.setStyleSheet(_BTN_ICON)
        self.btn_upload_here.clicked.connect(self._do_upload_here)

        self.btn_upload_folder_here = QPushButton()
        self.btn_upload_folder_here.setIcon(_icon('folder-upload', _C_PRIMARY, 15))
        self.btn_upload_folder_here.setIconSize(QSize(15, 15))
        self.btn_upload_folder_here.setToolTip(tr('Uploader un dossier ici'))
        self.btn_upload_folder_here.setStyleSheet(_BTN_ICON)
        self.btn_upload_folder_here.clicked.connect(self._do_upload_folder_here)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(_icon('trash-2', '#e74c3c', 15))
        self.btn_delete.setIconSize(QSize(15, 15))
        self.btn_delete.setToolTip(tr('Supprimer la sélection'))
        self.btn_delete.setStyleSheet(_BTN_ICON)
        self.btn_delete.clicked.connect(self._do_delete_selected)

        self.btn_rename = QPushButton()
        self.btn_rename.setIcon(_icon('edit-2', _C_MUTED, 15))
        self.btn_rename.setIconSize(QSize(15, 15))
        self.btn_rename.setToolTip(tr('Renommer'))
        self.btn_rename.setStyleSheet(_BTN_ICON)
        self.btn_rename.clicked.connect(self._do_rename_selected)

        btn_reload = QPushButton()
        btn_reload.setIcon(_icon('refresh', _C_MUTED, 15))
        btn_reload.setIconSize(QSize(15, 15))
        btn_reload.setToolTip(tr('Rafraîchir'))
        btn_reload.setStyleSheet(_BTN_ICON)
        btn_reload.clicked.connect(self._load_files)

        acts.addWidget(self.btn_open)
        acts.addWidget(self.btn_mkdir)
        acts.addWidget(self.btn_upload_here)
        acts.addWidget(self.btn_upload_folder_here)
        acts.addWidget(self.btn_delete)
        acts.addWidget(self.btn_rename)
        acts.addStretch()
        acts.addWidget(btn_reload)
        v.addWidget(self.barre_actions)

        # ── Section Publication ──────────────────────────────────────
        self.grp_publish = QGroupBox(tr('Publier vers Lizmap'))
        self.grp_publish.setStyleSheet(
            f'QGroupBox {{ font-weight: 600; font-size: 13px; color: {_C_TEXT};'
            f'  border: 1px solid {_C_BORDER}; border-radius: 8px; margin-top: 8px;'
            f'  padding-top: 10px; background: {_C_CARD}; }}'
            f'QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}'
        )
        pub_v = QVBoxLayout(self.grp_publish)
        pub_v.setSpacing(6)
        pub_v.setContentsMargins(10, 8, 10, 10)

        # Projet actif détecté dans QGIS
        row_local = QHBoxLayout()
        lbl_l = QLabel(tr('Projet actif :'))
        lbl_l.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; min-width: 90px;')
        self.lbl_local_project = QLabel(tr('Aucun projet ouvert dans QGIS'))
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_TEXT}; font-style: italic;'
        )
        self.lbl_local_project.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row_local.addWidget(lbl_l)
        row_local.addWidget(self.lbl_local_project, 1)
        pub_v.addLayout(row_local)

        # Chemin de destination sur le serveur
        row_dest = QHBoxLayout()
        lbl_d = QLabel(tr('Destination :'))
        lbl_d.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; min-width: 90px;')
        self.txt_publish_dest = QLineEdit()
        self.txt_publish_dest.setReadOnly(True)
        self.txt_publish_dest.setPlaceholderText(
            tr('Sélectionnez un fichier ou un dossier dans la liste ci-dessus')
        )
        row_dest.addWidget(lbl_d)
        row_dest.addWidget(self.txt_publish_dest, 1)
        pub_v.addLayout(row_dest)

        self.btn_valider = _btn(tr('Valider le projet'), 'check-circle',
                                _C_PRIMARY, _BTN_GHOST)
        self.btn_valider.setToolTip(
            tr('Fait examiner le projet par le serveur sans rien publier :\n'
            'connexions PostgreSQL, clefs primaires, index, projections,\n'
            'expressions, chemins locaux.')
        )
        self.btn_valider.setEnabled(False)
        self.btn_valider.clicked.connect(lambda: self._do_valider_projet())
        self.btn_publish = _btn(tr('Publier vers Lizmap'), 'upload-cloud', 'white', _BTN_SUCCESS)
        self.btn_publish.setToolTip(
            tr('Sauvegarde le projet QGIS actif et le publie sur le serveur.\n'
            'Fonctionne avec n\'importe quel projet ouvert dans QGIS.\n'
            'Lizmap recharge automatiquement.')
        )
        self.btn_publish.clicked.connect(self._do_publish_project)
        self.btn_publish.setEnabled(False)
        self.txt_publish_dest.textChanged.connect(
            lambda _t: self._sync_publish_button()
        )
        pub_v.addWidget(self.btn_valider)
        pub_v.addWidget(self.btn_publish)

        v.addWidget(self.grp_publish)

        # Rapport de validation. Il a d'abord ete une fenetre modale, qu'il
        # fallait fermer avant de corriger quoi que ce soit ; puis un panneau
        # sous la publication, qui chassait l'arbre des fichiers. Il occupe
        # maintenant son propre sous-onglet, ou la place ne se dispute pas.
        self.grp_validation = QGroupBox(tr('Validation du projet'))
        val_v = QVBoxLayout(self.grp_validation)
        val_v.setSpacing(8)

        self.lbl_validation = QLabel(
            tr("Aucun rapport pour l'instant. Ouvrez un projet, puis cliquez sur « Valider le projet », dans le gestionnaire de fichiers, ou ci-dessous."))
        self.lbl_validation.setWordWrap(True)
        self.lbl_validation.setStyleSheet('font-size: 13px;')
        val_v.addWidget(self.lbl_validation)

        self.lst_validation = QTreeWidget()
        self.lst_validation.setHeaderLabels(
            [tr('Gravité / couche'), tr('Catégorie'), tr('Constat')])
        entete_val = self.lst_validation.header()
        entete_val.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        entete_val.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        entete_val.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.lst_validation.setAlternatingRowColors(True)
        # Un constat tient rarement sur une ligne : il etait coupe net, et
        # il fallait selectionner la ligne pour le lire en entier. Le texte
        # passe donc a la ligne, et la hauteur des lignes s'ajuste.
        self.lst_validation.setWordWrap(True)
        self.lst_validation.setUniformRowHeights(False)
        # La selection prenait la premiere colonne seule, qui est vide sur
        # les lignes de signalement : un rectangle bleu isole, sans rapport
        # apparent avec la ligne lue.
        self.lst_validation.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        # La colonne d'arborescence — la ou se dessine la fleche de repli —
        # restait peinte du bleu de selection du systeme, en travers d'une
        # ligne dont le reste suivait la feuille de style : un rectangle
        # isole, sans rapport apparent avec la ligne lue.
        self.lst_validation.setStyleSheet(
            'QTreeWidget::branch:selected { background: transparent; }'
            'QTreeWidget::branch:hover { background: transparent; }'
        )
        # La page entiere est a lui : plus besoin de le plafonner pour
        # proteger l'arbre, qui vit maintenant dans l'autre sous-onglet.
        self.lst_validation.setMinimumHeight(160)
        self.lst_validation.currentItemChanged.connect(
            lambda *_: self._montrer_signalement())
        val_v.addWidget(self.lst_validation, 1)

        self.txt_validation = QTextEdit()
        self.txt_validation.setReadOnly(True)
        self.txt_validation.setMinimumHeight(110)
        self.txt_validation.setMaximumHeight(200)
        self.txt_validation.setPlaceholderText(
            tr('Sélectionnez un signalement pour voir la conséquence et la solution.'))
        val_v.addWidget(self.txt_validation)

        val_btns = QHBoxLayout()
        self.btn_valider_encore = _btn(tr('Relancer la validation'), 'check-circle',
                                       _C_PRIMARY, _BTN_GHOST)
        self.btn_valider_encore.clicked.connect(
            lambda: self._do_valider_projet())
        val_btns.addWidget(self.btn_valider_encore)
        self.btn_corriger = _btn(tr('Corriger dans QGIS'), 'tool',
                                 'white', _BTN_PRIMARY)
        self.btn_corriger.setToolTip(
            tr('Corrige dans le projet ouvert ce que le plugin sait corriger, '
               'après confirmation, puis relance la validation.'))
        self.btn_corriger.clicked.connect(self._corriger_dans_qgis)
        self.btn_corriger.setVisible(False)
        val_btns.addWidget(self.btn_corriger)
        val_btns.addStretch()
        btn_retour_fichiers = _btn(tr('Retour aux fichiers'), 'arrow-left',
                                   _C_MUTED, _BTN_GHOST)
        btn_retour_fichiers.clicked.connect(
            lambda: self.sous_onglets.setCurrentIndex(0))
        val_btns.addWidget(btn_retour_fichiers)
        val_v.addLayout(val_btns)

        defilement.setWidget(interieur)
        pf.addWidget(defilement)
        self.sous_onglets.addTab(page_fichiers, '  ' + tr('Gestionnaire de fichiers') + '  ')

        # ══ Sous-onglet 2 — Valider un projet ═════════════════════════
        page_validation = QWidget()
        pv = QVBoxLayout(page_validation)
        pv.setContentsMargins(10, 14, 10, 10)
        pv.setSpacing(8)

        self.grp_validation.setVisible(True)   # la page entiere lui revient
        pv.addWidget(self.grp_validation, 1)
        self.sous_onglets.addTab(page_validation, '  ' + tr('Valider un projet') + '  ')

        return tab

    # ── Onglet Upload ────────────────────────────────────────────────
    def _tab_upload(self):
        tab = QWidget()
        v   = QVBoxLayout(tab)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        grp = QGroupBox(tr('Uploader un dossier vers l\'instance'))
        f   = QFormLayout(grp)
        f.setSpacing(12)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        local_row = QHBoxLayout()
        local_row.setSpacing(6)
        self.txt_local = QLineEdit()
        self.txt_local.setPlaceholderText(tr('Sélectionner un dossier local…'))
        self.txt_local.setReadOnly(True)
        btn_browse = QPushButton()
        btn_browse.setIcon(_icon('folder', _C_MUTED, 15))
        btn_browse.setIconSize(QSize(15, 15))
        btn_browse.setStyleSheet(_BTN_ICON)
        btn_browse.clicked.connect(self._browse_folder)
        local_row.addWidget(self.txt_local)
        local_row.addWidget(btn_browse)
        f.addRow(_form_label(tr('Dossier local')), local_row)

        self.txt_remote = QLineEdit('/')
        self.txt_remote.setReadOnly(True)
        self.txt_remote.setPlaceholderText(tr('Sélectionnez un dossier local'))
        f.addRow(_form_label(tr('Destination')), self.txt_remote)
        v.addWidget(grp)

        self.btn_upload = _btn(tr('Uploader le dossier'), 'upload-cloud', 'white', _BTN_PRIMARY)
        self.btn_upload.clicked.connect(self._do_upload_folder)
        v.addWidget(self.btn_upload)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(8)
        self.lbl_progress = QLabel('')
        self.lbl_progress.setStyleSheet(f'color: {_C_MUTED}; font-size: 12px;')
        v.addWidget(self.progress)
        v.addWidget(self.lbl_progress)
        v.addStretch()
        return tab

    # ── Onglet PostGIS ───────────────────────────────────────────────
    def _tab_postgis(self):
        from qgis.PyQt.QtWidgets import QScrollArea

        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        info_frame = QFrame()
        # Selecteur restreint au cadre lui-meme : une regle QFrame nue
        # s'applique aussi aux enfants, et QLabel herite de QFrame — le
        # texte se retrouvait enferme dans une boite bordee.
        info_frame.setObjectName('lp_bandeau_info')
        info_frame.setStyleSheet(
            f'QFrame#lp_bandeau_info {{ background: {_C_INFO_BG}; '
            f'border: 1px solid #93C5FD; border-radius: 8px; padding: 2px; }}'
        )
        info_h = QHBoxLayout(info_frame)
        info_h.setContentsMargins(12, 10, 12, 10)
        info_ico = QLabel()
        info_ico.setPixmap(_icon('alert-circle', _C_INFO, 16).pixmap(16, 16))
        info_ico.setFixedSize(16, 16)
        info_ico.setStyleSheet('background: transparent;')
        info_lbl = QLabel(
            tr('Double-cliquez sur une table pour l\'ajouter comme couche dans QGIS.\n'
            'Connexion directe : QGIS → PostgreSQL de votre instance.')
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(
            f'color: {_C_INFO_TX}; font-size: 13px; background: transparent; '
            'border: none;'
        )
        info_h.addWidget(info_ico, 0, Qt.AlignmentFlag.AlignTop)
        info_h.addSpacing(8)
        info_h.addWidget(info_lbl)
        v.addWidget(info_frame)

        # Bandeau affiché quand PostGIS n'est pas disponible
        self.pg_unavailable = QFrame()
        self.pg_unavailable.setObjectName('lp_bandeau_alerte')
        self.pg_unavailable.setStyleSheet(
            f'QFrame#lp_bandeau_alerte {{ background: {_C_WARN_BG}; '
            f'border: 1px solid #FCD34D;'
            f'  border-radius: 8px; }}'
        )
        pu_h = QHBoxLayout(self.pg_unavailable)
        pu_h.setContentsMargins(12, 10, 12, 10)
        pu_ico = QLabel()
        pu_ico.setPixmap(_icon('alert-triangle', _C_WARN, 16).pixmap(16, 16))
        pu_ico.setFixedSize(16, 16)
        pu_ico.setStyleSheet('background: transparent;')
        pu_lbl = self.lbl_pg_indispo = QLabel(
            tr('PostGIS non disponible pour cette instance.\n'
            'L\'instance doit être déployée avec une base de données PostgreSQL/PostGIS\n'
            'pour utiliser cette fonctionnalité.')
        )
        pu_lbl.setWordWrap(True)
        pu_lbl.setStyleSheet(
            f'color: {_C_WARN_TX}; font-size: 13px; background: transparent;'
        )
        pu_h.addWidget(pu_ico, 0, Qt.AlignmentFlag.AlignTop)
        pu_h.addSpacing(8)
        pu_h.addWidget(pu_lbl)
        self.pg_unavailable.setVisible(False)
        v.addWidget(self.pg_unavailable)

        self.lst_pg = QTreeWidget()
        self.lst_pg.setHeaderLabels([tr('Table'), tr('Schéma'), tr('Géométrie'), tr('SRID')])
        self.lst_pg.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lst_pg.setAlternatingRowColors(True)
        self.lst_pg.setMinimumHeight(150)
        self.lst_pg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lst_pg.itemSelectionChanged.connect(self._sync_pg_buttons)
        self.lst_pg.itemDoubleClicked.connect(
            lambda item, _: self._add_postgis_layer(item)
        )
        # Les trois sections vont dans un separateur : leurs hauteurs
        # respectives dependent de ce qu'on regarde — la liste des tables,
        # le diagnostic, ou l'import — et l'utilisateur seul le sait.
        self.sections_pg = QSplitter(Qt.Orientation.Vertical)
        self.sections_pg.setChildrenCollapsible(False)
        self.sections_pg.setHandleWidth(8)

        bloc_tables = QWidget()
        bloc_tables_v = QVBoxLayout(bloc_tables)
        bloc_tables_v.setContentsMargins(0, 0, 0, 0)
        bloc_tables_v.setSpacing(8)
        bloc_tables_v.addWidget(self.lst_pg, 1)

        btns = QHBoxLayout()
        self.btn_load_pg = _btn(tr('Charger les tables'), 'refresh', _C_PRIMARY, _BTN_GHOST)
        self.btn_load_pg.clicked.connect(self._load_postgis_tables)
        self.btn_add_pg = _btn(tr('Ajouter à QGIS'), 'plus-circle', 'white', _BTN_SUCCESS)
        self.btn_add_pg.setEnabled(False)
        self.btn_add_pg.clicked.connect(
            lambda: self._add_postgis_layer(self.lst_pg.currentItem())
        )
        self.btn_diag_pg = _btn(tr('Diagnostiquer la base'), 'activity',
                                _C_PRIMARY, _BTN_GHOST)
        self.btn_diag_pg.setToolTip(
            tr('Analyse la base sans rien y modifier : index manquants, '
            'statistiques périmées, géométries trop détaillées…')
        )
        self.btn_diag_pg.clicked.connect(self._do_diagnostic_db)
        btns.addWidget(self.btn_load_pg)
        btns.addWidget(self.btn_diag_pg)
        btns.addStretch()
        btns.addWidget(self.btn_add_pg)
        bloc_tables_v.addLayout(btns)
        self.sections_pg.addWidget(bloc_tables)

        # ── Section Import dans PostGIS ──────────────────────────
        # ── Santé de la base ──────────────────────────────────────
        self.grp_sante = QGroupBox(tr('Santé de la base'))
        self.grp_sante.setVisible(False)
        sante_v = QVBoxLayout(self.grp_sante)
        sante_v.setSpacing(8)

        self.lbl_sante = QLabel('')
        self.lbl_sante.setWordWrap(True)
        self.lbl_sante.setStyleSheet(f'font-size: 13px; color: {_C_MUTED};')
        sante_v.addWidget(self.lbl_sante)

        self.lst_sante = QTreeWidget()
        self.lst_sante.setHeaderLabels([tr('Table'), tr('Problème'), tr('Correction'), tr('Détail')])
        entete = self.lst_sante.header()
        # Les trois premieres colonnes s'ajustent a leur contenu, sans quoi
        # « Index spatial manquant » s'affichait « Index spatia… ».
        for colonne in (0, 1, 2):
            entete.setSectionResizeMode(colonne, QHeaderView.ResizeMode.ResizeToContents)
        entete.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.lst_sante.setAlternatingRowColors(True)
        self.lst_sante.setMinimumHeight(140)
        self.lst_sante.setRootIsDecorated(False)
        self.lst_sante.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst_sante.itemSelectionChanged.connect(self._sync_optim_buttons)
        sante_v.addWidget(self.lst_sante, 1)

        sante_btns = QHBoxLayout()
        self.btn_optim_sel = _btn(tr('Optimiser la sélection'), 'zap',
                                  _C_PRIMARY, _BTN_GHOST)
        self.btn_optim_sel.setEnabled(False)
        self.btn_optim_sel.clicked.connect(
            lambda: self._do_optimiser_db(selection_seule=True)
        )
        self.btn_optim_pg = _btn(tr('Tout optimiser'), 'zap', 'white', _BTN_SUCCESS)
        self.btn_optim_pg.setEnabled(False)
        self.btn_optim_pg.clicked.connect(
            lambda: self._do_optimiser_db(selection_seule=False)
        )
        self.btn_export_sante = _btn(tr('Exporter'), 'download',
                                     _C_MUTED, _BTN_GHOST)
        self.btn_export_sante.setEnabled(False)
        self.btn_export_sante.setToolTip(
            tr('Enregistrer le diagnostic : rapport CSV, ou script SQL rejouable')
        )
        self.btn_export_sante.clicked.connect(self._do_exporter_sante)
        sante_btns.addWidget(self.btn_optim_sel)
        sante_btns.addWidget(self.btn_optim_pg)
        sante_btns.addStretch()
        sante_btns.addWidget(self.btn_export_sante)
        sante_v.addLayout(sante_btns)
        self.sections_pg.addWidget(self.grp_sante)

        import_grp = QGroupBox(tr('Importer une couche dans PostGIS'))
        ig = QVBoxLayout(import_grp)
        ig.setSpacing(8)
        ig.setContentsMargins(12, 14, 12, 12)

        # Ligne 1 : Couche QGIS
        lbl_layer = QLabel(tr('Couche QGIS'))
        lbl_layer.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        ig.addWidget(lbl_layer)
        layer_row = QHBoxLayout()
        layer_row.setSpacing(6)
        self.cmb_import_layer = QComboBox()
        _liste_deroulante(self.cmb_import_layer)
        self.cmb_import_layer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cmb_import_layer.setMinimumWidth(0)
        self.cmb_import_layer.currentIndexChanged.connect(self._on_import_layer_changed)
        btn_refresh_layers = QPushButton()
        btn_refresh_layers.setIcon(_icon('refresh', _C_MUTED, 15))
        btn_refresh_layers.setIconSize(QSize(15, 15))
        btn_refresh_layers.setToolTip(tr('Rafraîchir la liste des couches'))
        btn_refresh_layers.setStyleSheet(_BTN_ICON)
        btn_refresh_layers.clicked.connect(self._refresh_import_layers)
        layer_row.addWidget(self.cmb_import_layer, 1)
        layer_row.addWidget(btn_refresh_layers, 0)
        ig.addLayout(layer_row)

        # Ligne 2 : Schéma + Table (côte à côte, responsive)
        schema_table_row = QHBoxLayout()
        schema_table_row.setSpacing(10)

        schema_col = QVBoxLayout()
        schema_col.setSpacing(3)
        lbl_schema = QLabel(tr('Schéma'))
        lbl_schema.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        self.txt_import_schema = QLineEdit()
        self.txt_import_schema.setPlaceholderText(tr('schéma cible'))
        self.txt_import_schema.textChanged.connect(
            lambda _t: self._sync_pg_buttons()
        )
        schema_col.addWidget(lbl_schema)
        schema_col.addWidget(self.txt_import_schema)
        schema_table_row.addLayout(schema_col, 1)

        table_col = QVBoxLayout()
        table_col.setSpacing(3)
        lbl_table = QLabel(tr('Table'))
        lbl_table.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        self.txt_import_table = QLineEdit()
        self.txt_import_table.setPlaceholderText('nom_table')
        self.txt_import_table.textChanged.connect(
            lambda _t: self._sync_pg_buttons()
        )
        table_col.addWidget(lbl_table)
        table_col.addWidget(self.txt_import_table)
        schema_table_row.addLayout(table_col, 2)

        ig.addLayout(schema_table_row)

        # Bouton import (dans le GroupBox, pleine largeur)
        self.btn_import_pg = _btn(tr('Importer dans PostGIS'), 'upload', 'white', _BTN_PRIMARY)
        self.btn_import_pg.setEnabled(False)
        self.btn_import_pg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_import_pg.setToolTip(
            tr('Envoyer la couche sélectionnée dans la base PostGIS de l\'instance')
        )
        self.btn_import_pg.clicked.connect(self._do_import_to_postgis)
        ig.addWidget(self.btn_import_pg)

        self.sections_pg.addWidget(import_grp)
        v.addWidget(self.sections_pg, 1)
        self._restaurer_sections_pg()

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════
    # Actions — Connexion
    # ══════════════════════════════════════════════════════════════════

    def _mode_entreprise(self):
        return self.cmb_serveur.currentData() == 'entreprise'

    def _sync_support(self):
        """Le bouton de support mène au support de LizPack, ou, sur le
        portail d'une organisation, à celui qu'elle a renseigné (adresse
        web, sinon courriel). Sans contact renseigné, la ligne disparaît :
        renvoyer vers LizPack les utilisateurs d'un serveur qu'il
        n'administre pas les mettrait dans une impasse."""
        if not self._mode_entreprise():
            self._support_url = _SUPPORT_URL
            self.btn_support.setText(tr('Contacter le support'))
            self.btn_support.setToolTip('')
            self.ligne_support.setVisible(True)
            return
        b = getattr(self.session, 'branding', None) or {}
        url = (b.get('support_url') or '').strip()
        courriel = (b.get('support_email') or '').strip()
        tel = (b.get('support_phone') or '').strip()
        if url and not url.lower().startswith(('http://', 'https://')):
            url = 'https://' + url
        cible = url or (('mailto:' + courriel) if courriel else '')
        self.ligne_support.setVisible(bool(cible))
        if not cible:
            return
        self._support_url = cible
        org = (b.get('company_name') or b.get('brand_name') or '').strip()
        self.btn_support.setText(tr('Contacter le support de {0}', org) if org
                                 else tr('Contacter le support'))
        self.btn_support.setToolTip(' · '.join(x for x in (url, courriel, tel) if x))

    def _sync_mode_serveur(self):
        """Montre les champs du serveur choisi, et eux seuls."""
        ent = self._mode_entreprise()
        if hasattr(self, 'ligne_support'):
            self._sync_support()
        for lbl in (self.lbl_email, self.lbl_pwd):
            lbl.parentWidget().setVisible(not ent)
        for lbl in (self.lbl_portail, self.lbl_jeton, self.lbl_certificat):
            lbl.parentWidget().setVisible(ent)
        # Pas de changement de serveur en pleine session.
        self.cmb_serveur.setEnabled(not self.session.is_authenticated())

    def _choisir_certificat(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, tr("Certificat de l'autorité de certification"), '',
            tr('Certificats (*.pem *.crt *.cer);;Tous les fichiers (*)'))
        if chemin:
            self.txt_certificat.setText(chemin)

    def _do_login(self):
        if self._mode_entreprise():
            adresse = normaliser_adresse(self.txt_portail.text())
            jeton = self.txt_jeton.text().strip()
            certificat = self.txt_certificat.text().strip()
            if not adresse or not jeton:
                self._log(tr("Adresse du portail et jeton d'API requis."), 'warn')
                return
            if certificat and not os.path.isfile(certificat):
                self._log(tr('Certificat introuvable : {}').format(certificat), 'warn')
                return
            self.txt_portail.setText(adresse)
            self.session = SessionEntreprise(adresse, certificat)
            email, password = '', jeton
        else:
            email    = self.txt_email.text().strip()
            password = self.txt_pwd.text()
            if not email or not password:
                self._log(tr('Email et mot de passe requis.'), 'warn')
                return
            if getattr(self.session, 'entreprise', False):
                self.session = LizpackSession()
        self.btn_login.setEnabled(False)
        self.btn_login.setText(tr('Connexion…'))
        self._log(tr('Authentification en cours…'))
        self._login_worker = LoginWorker(self.session, email, password)
        self._login_worker.finished.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._start_loading(tr('Authentification…'))
        self._login_worker.finished.connect(lambda _: self._stop_loading())
        self._login_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._login_worker)
        self._login_worker.start()

    def _peupler_espaces(self):
        """Remplit le choix d'espace : le sien, puis les equipes."""
        equipes = getattr(self.session, 'memberships', []) or []
        self.cmb_espace.blockSignals(True)
        self.cmb_espace.clear()
        self.cmb_espace.addItem(tr('Mon compte'), userData=None)
        for equipe in equipes:
            nom = equipe.get('owner_name') or equipe.get('owner_email') or '?'
            role = equipe.get('role_display') or equipe.get('role') or ''
            libelle = f'{nom}  ({role})' if role else nom
            self.cmb_espace.addItem(libelle, userData=equipe.get('owner_id'))
        self.cmb_espace.blockSignals(False)

        visible = bool(equipes)
        self.lbl_espace.parentWidget().setVisible(visible)
        if visible:
            self._log(
                tr('{0} espace(s) partagé(s) disponible(s).', len(equipes)), 'ok',
            )

    def _on_espace_change(self, _index):
        """Recharge la liste des instances dans le nouvel espace."""
        owner = self.cmb_espace.currentData()
        if owner == self.session.team_owner_id:
            return
        self._reset_instance_state()
        self.session.set_team_context(owner)
        nom = self.cmb_espace.currentText()
        self._log(tr('Espace : {0}…', nom))
        self._recharger_instances()

    def _recharger_instances(self):
        """Redemande la liste des instances dans le contexte courant."""
        self.cmb_instance.blockSignals(True)
        self.cmb_instance.clear()
        self.cmb_instance.blockSignals(False)
        self._sync_connect_button()
        self._espace_worker = ListeInstancesWorker(self.session)
        self._espace_worker.finished.connect(self._on_instances_rechargees)
        self._espace_worker.error.connect(lambda e: self._log(e, 'error'))
        self._start_loading(tr('Chargement des instances…'))
        self._espace_worker.finished.connect(lambda _: self._stop_loading())
        self._espace_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._espace_worker)
        self._espace_worker.start()

    def _on_instances_rechargees(self, instances):
        """Meme traitement qu'apres une authentification, sans la refaire."""
        self._remplir_instances(instances)
        self._appliquer_permissions()

    def _refus_jeton_lecture(self):
        if self._jeton_lecture:
            self._log(_MSG_JETON_LECTURE, 'warn')
            return True
        return False

    def _appliquer_permissions(self):
        """Bride l'interface sur ce que le serveur autorise.

        Un membre d'equipe peut n'avoir que la lecture. Laisser les
        boutons actifs le ferait buter sur un refus du serveur apres
        coup, sans savoir pourquoi.
        """
        acces_fichiers = self.session.peut('can_manage_files')
        self._lecture_seule = not acces_fichiers

        # Le serveur refuse TOUT le gestionnaire de fichiers sans ce droit,
        # y compris le listage : il n'existe pas de demi-mesure a offrir.
        # Ne nommer l'espace que si l'on est bien dans celui d'une equipe :
        # « Mon compte » n'aurait aucun sens dans ce message.
        nom_espace = ''
        if getattr(self.session, 'team_owner_id', None):
            nom_espace = self.cmb_espace.currentText()
        self.lbl_fichiers_interdits.setText(
            tr("Cet espace ne vous donne pas accès aux fichiers.\nLe rôle qui vous est attribué{0} ne comprend pas la gestion des fichiers : ni la consultation, ni le téléchargement. Demandez la permission au propriétaire de l'espace.", f' dans « {nom_espace} »' if nom_espace else '')
        )
        self.fichiers_interdits.setVisible(not acces_fichiers)
        self.tree.setVisible(acces_fichiers)
        self.barre_nav.setVisible(acces_fichiers)
        self.barre_actions.setVisible(acces_fichiers)
        self.grp_publish.setVisible(acces_fichiers)

        for bouton in (self.btn_upload_here, self.btn_upload_folder_here,
                       self.btn_mkdir, self.btn_delete, self.btn_rename,
                       self.btn_publish, self.btn_upload, self.btn_open,
                       self.btn_import_pg, self.btn_optim_pg, self.btn_optim_sel):
            if not acces_fichiers:
                bouton.setEnabled(False)
                bouton.setToolTip(
                    tr('Cet espace ne vous donne pas accès aux fichiers.')
                )

        # Jeton d'API en lecture seule (serveur de son organisation) : on
        # parcourt, ouvre et valide ; rien ne s'écrit sur le serveur.
        self._jeton_lecture = acces_fichiers and not getattr(self.session, 'ecriture', True)
        if self._jeton_lecture:
            for bouton in (self.btn_upload_here, self.btn_upload_folder_here,
                           self.btn_mkdir, self.btn_delete, self.btn_rename,
                           self.btn_publish, self.btn_upload):
                bouton.setEnabled(False)
                bouton.setToolTip(_MSG_JETON_LECTURE)
            self._log(tr('{0} Vous pouvez parcourir, ouvrir et valider les projets.', _MSG_JETON_LECTURE), 'warn')
        elif acces_fichiers:
            # Session précédente en lecture seule : ce qu'elle avait grisé
            # ne se rallumait jamais (Upload restait désactivé).
            for bouton in (self.btn_upload_here, self.btn_upload_folder_here,
                           self.btn_mkdir, self.btn_upload):
                bouton.setEnabled(True)
                bouton.setToolTip('')
            for bouton in (self.btn_delete, self.btn_rename, self.btn_publish):
                bouton.setToolTip('')

        # L'onglet Upload n'a plus rien a offrir non plus.
        self.tabs.setTabEnabled(2, acces_fichiers and not self._jeton_lecture)
        if not acces_fichiers and self.session.permissions:
            self._log(
                tr('Cet espace ne vous donne pas accès aux fichiers : '
                "l'onglet Projets et l'onglet Upload sont désactivés. "
                "L'onglet PostGIS reste disponible."),
                'warn',
            )

    def _on_login_success(self, instances):
        self.btn_login.setText(tr('Se connecter'))
        self._sync_support()
        reglages = QSettings()
        reglages.setValue(_MODE_CLE, self.cmb_serveur.currentData())
        if self._mode_entreprise():
            reglages.setValue(_PORTAIL_CLE, self.txt_portail.text().strip())
            reglages.setValue(_CERTIFICAT_CLE, self.txt_certificat.text().strip())
            moi = getattr(self.session, 'moi', {}) or {}
            if moi.get('username'):
                self._log(tr('Connecté au portail : {}.').format(moi['username']), 'ok')
        self._sync_mode_serveur()
        if self.chk_souvenir.isChecked():
            if self._mode_entreprise():
                self._enregistrer_identifiants(
                    self.txt_portail.text().strip(), self.txt_jeton.text().strip(),
                    _AUTHCFG_JETON_CLE, enregistrer_email=False)
            else:
                self._enregistrer_identifiants(
                    self.txt_email.text().strip(), self.txt_pwd.text()
                )
        if instances:
            self._log(tr('{0} instance(s) disponible(s).', len(instances)), 'ok')
        elif getattr(self.session, 'entreprise', False):
            self._log(tr("Aucune instance ouverte à ce compte. Demandez à "
                      "l'administrateur du portail de vous ouvrir une instance "
                      '(fiche de l\'instance > Accès).'), 'warn')
        else:
            self._log(tr('Aucune instance sur ce compte.'), 'warn')
        self._peupler_espaces()
        self._remplir_instances(instances)
        if not instances:
            self.cmb_instance.setPlaceholderText(tr('Aucune instance accessible'))
        self.btn_logout.setEnabled(True)
        self.btn_login.setEnabled(False)
        self._appliquer_permissions()
        self._refresh_auth_state()

    def _remplir_instances(self, instances):
        """Remplit la liste deroulante des instances."""
        self.cmb_instance.blockSignals(True)
        self.cmb_instance.clear()
        self._instances_data = instances
        for inst in instances:
            status = inst.get('status', '')
            if status == 'RUNNING':
                dot = '● '
            elif status.startswith('SUSPENDED'):
                dot = '⊘ '
            else:
                dot = '○ '
            label_status = {
                'RUNNING': tr('En cours'),
                'STOPPED': tr('Arrêtée'),
                'SUSPENDED_BILLING': tr('Suspendue (abonnement)'),
                'SUSPENDED_QUOTA': tr('Suspendue (quota)'),
                'SUSPENDED': tr('Suspendue'),
                'DEPLOYING': tr('Déploiement…'),
                'ERROR': tr('Erreur'),
            }.get(status, status)
            self.cmb_instance.addItem(
                tr('{0}{1}  ({2})', dot, inst['name'], label_status), userData=inst
            )
        self.cmb_instance.blockSignals(False)
        self.grp_instance.setEnabled(True)
        self._sync_connect_button()
        self.btn_logout.setEnabled(True)
        self.btn_login.setEnabled(False)
        self._refresh_auth_state()

    def _on_login_error(self, msg):
        self.btn_login.setEnabled(True)
        self.btn_login.setText(tr('Se connecter'))
        self._log(msg.strip(), 'error')

    def _sync_connect_button(self):
        """Active « Connecter à l'instance » seulement quand cela a un sens.

        Une fois connecte, reappuyer sur le bouton ne ferait que refaire le
        meme travail : le bouton reste donc grise tant que la selection
        n'a pas change. Il redevient actif si l'utilisateur choisit une
        autre instance, ou apres une deconnexion.
        """
        # Rafraichir n'a de sens qu'une fois connecte, et reste possible
        # meme si la liste deroulante pointe ailleurs.
        self.btn_rafraichir.setEnabled(self.session.is_connected())

        inst = self.cmb_instance.currentData()
        if not inst:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setToolTip('')
            return

        deja_connecte = (
            self.session.is_connected()
            and inst.get('id') == self.session.instance_id
        )
        self.btn_connect.setEnabled(not deja_connecte)
        self.btn_connect.setToolTip(
            tr('Déjà connecté à « {0} » : choisissez une autre instance pour changer.', inst['name'])
            if deja_connecte else
            tr('Se connecter à « {0} »', inst['name'])
        )

    def _do_rafraichir_connexion(self):
        """Rejoue la connexion a l'instance deja connectee.

        Les identifiants de la base, le quota et les permissions sont
        lus au moment de la connexion : une modification faite depuis le
        site ne parvenait au plugin qu'en se deconnectant. Rafraichir
        redemande le tout sans changer d'instance.
        """
        if not self.session.is_connected():
            self._log(tr('Aucune instance connectee.'), 'warn')
            return

        identifiant = self.session.instance_id
        nom = self.session.instance_name
        self.btn_rafraichir.setEnabled(False)
        self._log(tr('Rafraîchissement de {}…').format(nom))

        # Le cache de listage decrit l'etat d'avant : le garder ferait
        # afficher les anciens fichiers apres un rafraichissement.
        try:
            self.session.clear_cache()
        except Exception as e:
            journal.ignorer(e, 'vidage du cache de listage')

        self._connect_worker = ConnectInstanceWorker(
            self.session, identifiant, nom)
        self._connect_worker.finished.connect(self._on_instance_connected)
        self._connect_worker.error.connect(self._on_instance_connect_error)
        self._start_loading(tr('Rafraîchissement de {}…').format(nom))
        self._connect_worker.finished.connect(lambda: self._stop_loading())
        self._connect_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._connect_worker)
        self._connect_worker.start()

    def _do_connect_instance(self):
        inst = self.cmb_instance.currentData()
        if not inst:
            self._log(tr('Sélectionnez une instance.'), 'warn')
            return

        status = inst.get('status', '').upper()
        if status == 'SUSPENDED_BILLING':
            self._log(
                tr('Cette instance est suspendue (abonnement expiré).\n'
                'Renouvelez votre abonnement depuis votre espace client '
                '(Facturation) pour réactiver l\'instance.'),
                'error',
            )
            return
        if status == 'SUSPENDED_QUOTA':
            self._log(
                tr('Cette instance est suspendue (quota dépassé).\n'
                'Vous avez dépassé les limites de stockage de votre plan.\n'
                'La base de données PostgreSQL reste accessible pour '
                'vous permettre de libérer de l\'espace.\n'
                'Supprimez des données puis vérifiez votre quota depuis '
                'votre espace client.'),
                'error',
            )
            # On autorise la connexion pour que l'onglet PostGIS reste utilisable
            self._quota_suspended = True
        elif status == 'SUSPENDED':
            self._log(
                tr('Cette instance est suspendue.\n'
                'Vérifiez votre abonnement depuis votre espace client '
                '(Facturation) pour réactiver l\'instance.'),
                'error',
            )
            return
        elif status == 'STOPPED':
            self._log(
                tr('Cette instance est arrêtée.\n'
                'Démarrez-la depuis votre tableau de bord avant de vous connecter.'),
                'warn',
            )
            return
        elif status not in ('RUNNING', 'DEPLOYING'):
            self._log(
                tr('Instance indisponible (statut : {0}).\nVérifiez son état depuis votre tableau de bord.', status),
                'warn',
            )
            return
        else:
            self._quota_suspended = False

        # Réinitialiser l'état de l'instance précédente si on change
        if self.session.is_connected():
            prev = self.session.instance_name
            self._log(tr('Déconnexion de « {0} »…', prev))
            self._reset_instance_state()

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText(tr('Connexion…'))
        self._log(tr('Connexion à "{0}"…', inst['name']))
        self._connect_worker = ConnectInstanceWorker(
            self.session, inst['id'], inst['name']
        )
        self._connect_worker.finished.connect(self._on_instance_connected)
        self._connect_worker.error.connect(self._on_instance_connect_error)
        self._start_loading(tr('Connexion à "{0}"…', inst['name']))
        self._connect_worker.finished.connect(lambda: self._stop_loading())
        self._connect_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._connect_worker)
        self._connect_worker.start()

    def _on_instance_connected(self):
        self.btn_connect.setText(tr("Connecter à l'instance"))
        name = self.session.instance_name
        self.lbl_instance_info.setText(tr('Instance connectée : {0}', name))
        self._log(tr('Connecté à {0}', name), 'ok')
        if getattr(self.session, 'metadata_error', ''):
            self._log(
                tr("Informations de l'instance indisponibles : {0}.\nL'onglet PostGIS restera vide et la publication ne pourra pas réécrire les connexions du projet.", self.session.metadata_error.rstrip(".")),
                'warn',
            )
        self._current_path = '/'
        self._path_history = []
        self._sync_connect_button()
        self._sync_publish_button()
        self._sync_postgis_etat()
        self._refresh_auth_state()
        self._register_qgis_pg_connection()
        self._refresh_import_layers()
        self._load_files()

    def _on_instance_connect_error(self, msg):
        self.btn_connect.setText(tr("Connecter à l'instance"))
        self._sync_connect_button()
        self._log(msg.strip(), 'error')

    def _register_qgis_pg_connection(self):
        """Enregistre une connexion PostgreSQL dans QGIS automatiquement
        pour que les couches PostGIS fonctionnent sans configuration manuelle."""
        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user']]):
            return
        # Sans mot de passe (droit absent), la connexion échouerait dans
        # l'explorateur : ne pas l'enregistrer.
        if not pg.get('password'):
            return
        conn_name = f'LizPack - {self.session.instance_name}'

        # L'API du fournisseur d'abord : saveConnection() reecrit le groupe
        # de reglages a partir de l'URI et perd les drapeaux d'enregistrement
        # des identifiants. Ecrits avant, ils disparaissaient ; QGIS ne
        # reutilisait alors ni l'utilisateur ni le mot de passe, et
        # l'explorateur affichait « La connexion a echoue ».
        self._prevenir_explorateur(conn_name, pg)

        # Ne restent a ecrire que l'adresse, les identifiants et les deux
        # drapeaux. `sslmode` est laisse tel que le fournisseur l'a pose : il
        # attend le nom de la valeur, pas son rang, et ecrire 2 par-dessus
        # « SslPrefer » rendait le reglage illisible.
        s = QSettings()
        prefix = f'PostgreSQL/connections/{conn_name}'
        s.setValue(f'{prefix}/host', pg['host'])
        s.setValue(f'{prefix}/port', pg['port'])
        s.setValue(f'{prefix}/database', pg['dbname'])
        s.setValue(f'{prefix}/username', pg['user'])
        s.setValue(f'{prefix}/password', pg['password'])
        s.setValue(f'{prefix}/saveUsername', True)
        s.setValue(f'{prefix}/savePassword', True)
        self._registered_pg_conn = conn_name
        self._log(tr('Connexion PostgreSQL « {0} » enregistrée dans QGIS.', conn_name), 'ok')
        # L'explorateur ne reconstruit pas son arbre de lui-meme, et le
        # plugin ne le forcera pas : reload() faisait tomber QGIS, refresh()
        # sur ce noeud le fige le temps d'essayer chaque connexion, celles
        # qui echouent comprises. Reste a le dire.
        self._log(
            tr("Pour la voir dans l'explorateur : clic droit sur PostgreSQL "
            '→ Rafraîchir.'))

    def _prevenir_explorateur(self, nom, pg):
        """Signale a QGIS qu'une connexion PostgreSQL a change.

        Surtout : ne PAS appeler iface.browserModel().reload(). Cet appel
        reconstruit l'arbre de l'explorateur sous les pieds de QGIS et le
        fait tomber — deux rapports de plantage le designent, l'un en
        « Fatal Python error: Aborted », l'autre en exception Windows
        0xc0000374 (corruption du tas).

        L'API du fournisseur emet le signal que l'explorateur ecoute : il
        se rafraichit de lui-meme, au bon moment. Si elle n'est pas
        disponible, on ne force rien : la connexion est deja ecrite, elle
        apparaitra au prochain rafraichissement de l'explorateur.
        """
        try:
            meta = QgsProviderRegistry.instance().providerMetadata('postgres')
            if meta is None:
                return
            if pg is None:
                meta.deleteConnection(nom)
                return
            uri = QgsDataSourceUri()
            uri.setConnection(
                pg['host'], str(pg['port']), pg['dbname'], pg['user'], pg['password'],
            )
            meta.saveConnection(meta.createConnection(uri.uri(False), {}), nom)
        except Exception as e:
            # L'explorateur se rafraichira de lui-meme au prochain passage.
            journal.ignorer(e, 'notification de l\'explorateur QGIS')

    def _unregister_qgis_pg_connection(self):
        """Supprime la connexion PostgreSQL enregistrée par le plugin."""
        conn_name = self._registered_pg_conn
        if not conn_name:
            return
        s = QSettings()
        s.remove(f'PostgreSQL/connections/{conn_name}')
        self._registered_pg_conn = None
        self._prevenir_explorateur(conn_name, None)

    def _oublier_connexions_pg(self):
        """Retire toutes les connexions posees par le plugin.

        `_unregister_qgis_pg_connection` ne connait que celle de la session
        en cours : une connexion posee avant un redemarrage de QGIS, ou
        avant un rechargement du plugin, n'etait plus reclamee par personne
        et restait dans l'explorateur, morte — le mot de passe de son
        instance ayant pu changer entre temps.

        Toutes portent le meme prefixe, et c'est le plugin qui les ecrit :
        les balayer a la deconnexion ne touche a rien d'autre.
        """
        reglages = QSettings()
        reglages.beginGroup('PostgreSQL/connections')
        noms = [n for n in reglages.childGroups() if n.startswith('LizPack - ')]
        reglages.endGroup()
        for nom in noms:
            reglages.remove('PostgreSQL/connections/{}'.format(nom))
            self._prevenir_explorateur(nom, None)
        self._registered_pg_conn = None
        if noms:
            self._log(tr('{} connexion(s) PostgreSQL retirée(s) de QGIS.').format(
                len(noms)))

    def _reset_instance_state(self):
        """Nettoie tout l'état lié à l'instance courante (fichiers, PostGIS, quota, chemins)."""
        self._unregister_qgis_pg_connection()
        self.tree.clear()
        self.lst_pg.clear()
        # La sante de la base decrit l'instance quittee : la laisser a
        # l'ecran ferait croire qu'elle vaut encore pour la suivante.
        self.lst_sante.clear()
        self.lbl_sante.setText('')
        self.grp_sante.setVisible(False)
        self._problemes = []
        self._open_project_api_path = None
        self._current_path = '/'
        self._path_history = []
        self._clipboard_ids = None
        self._clipboard_mode = 'copy'
        self._quota_suspended = False
        self.lbl_instance_info.setText('')
        self.lbl_local_project.setText(tr('Aucun projet ouvert dans QGIS'))
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_MUTED}; font-style: italic;'
        )
        self.txt_publish_dest.clear()
        self._sync_publish_button()
        self.txt_import_schema.clear()
        self.txt_import_table.clear()
        self._sync_postgis_etat()

    def _do_logout_nettoyage(self):
        """Rend l'acces complet quand on quitte un espace partage."""
        self._lecture_seule = False
        self.fichiers_interdits.setVisible(False)
        self.tree.setVisible(True)
        self.barre_nav.setVisible(True)
        self.barre_actions.setVisible(True)
        self.grp_publish.setVisible(True)
        self.tabs.setTabEnabled(2, True)

    def _do_logout(self):
        self._reset_instance_state()
        # La deconnexion emporte la base : laisser la connexion derriere soi
        # promettait un acces que le plugin ne garantit plus.
        self._oublier_connexions_pg()
        self._do_logout_nettoyage()
        self.session.logout()
        self.cmb_espace.clear()
        self.lbl_espace.parentWidget().setVisible(False)
        self.cmb_instance.clear()
        self.grp_instance.setEnabled(False)
        self.btn_connect.setEnabled(False)
        self.btn_login.setEnabled(True)
        self.btn_logout.setEnabled(False)
        self._refresh_auth_state()
        self._sync_mode_serveur()
        self._sync_support()
        self._log(tr('Déconnecté.'))

    # ══════════════════════════════════════════════════════════════════
    # Actions — Projets
    # ══════════════════════════════════════════════════════════════════

    def _do_open_project(self):
        item = self.tree.currentItem()
        if not item:
            self._log(tr('Sélectionnez un fichier dans la liste.'), 'warn')
            return
        api_path = item.data(0, Qt.ItemDataRole.UserRole)
        file_id  = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not api_path or not api_path.lower().endswith(('.qgz', '.qgs')):
            self._log(tr('Sélectionnez un fichier .qgz ou .qgs.'), 'warn')
            return
        fname      = os.path.basename(api_path)
        server_dir = '/'.join(api_path.rstrip('/').split('/')[:-1]) or '/'

        # Le projet et tout son dossier sont rapatries. A la racine, cela
        # reviendrait a aspirer l'instance entiere : on previent avant.
        if server_dir == '/':
            rep = QMessageBox.question(
                self, tr('Télécharger tout le contenu ?'),
                tr("Ce projet est à la racine de l'instance.\n"
                'Ouvrir revient à télécharger tout son contenu.\n\n'
                'Continuer ?'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if rep != QMessageBox.StandardButton.Yes:
                self._log(tr('Ouverture annulée.'), 'warn')
                return

        # Demander ou enregistrer, en repartant du repertoire de travail.
        dossier = QFileDialog.getExistingDirectory(
            self, tr('Où enregistrer le projet ?'), self._repertoire_travail(),
        )
        if not dossier:
            self._log(tr('Ouverture annulée.'), 'warn')
            return
        self._definir_repertoire_travail(dossier)

        # Recreer le dossier serveur sous la destination choisie, pour que
        # les chemins relatifs du projet restent valides.
        nom_dossier = os.path.basename(server_dir.rstrip('/')) or self.session.instance_name
        local_dir   = os.path.join(dossier, nom_dossier)
        local_path  = os.path.join(local_dir, fname)
        os.makedirs(local_dir, exist_ok=True)
        self._log(tr('Destination : {0}', local_dir))
        self._log(tr('Téléchargement de {0} + données associées…', fname))
        self.btn_open.setEnabled(False)
        self._dl_worker = DownloadProjectWorker(self.session, file_id, local_path, api_path)
        self._dl_worker.finished.connect(self._on_project_downloaded)
        self._dl_worker.status.connect(lambda msg: self._log(msg))
        self._dl_worker.error.connect(
            lambda e: (self._log(e, 'error'), self._sync_open_button())
        )
        self._start_loading(tr('Téléchargement de {0}…', fname))
        self._dl_worker.finished.connect(lambda _: self._stop_loading())
        self._dl_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._dl_worker)
        self._dl_worker.start()

    def _authcfg_bd(self, pg):
        """Range les identifiants de la base dans le magasin de QGIS.

        Retourne l'identifiant de configuration a poser dans les couches,
        ou une chaine vide si le magasin n'est pas disponible. La
        configuration est reutilisee d'un projet a l'autre : son
        identifiant doit rester stable, sans quoi les projets deja ouverts
        pointeraient vers une configuration disparue.
        """
        reglages = QSettings()
        cle = '{}/{}'.format(_AUTHCFG_BD_CLE, self.session.instance_name)
        try:
            gestionnaire = QgsApplication.authManager()
            config = QgsAuthMethodConfig()
            config.setName('LizPack — {} (base)'.format(self.session.instance_name))
            config.setMethod('Basic')
            config.setConfig('username', pg['user'])
            config.setConfig('password', pg['password'])

            ancien = reglages.value(cle, '') or ''
            if ancien and ancien in gestionnaire.configIds():
                config.setId(ancien)
                if gestionnaire.updateAuthenticationConfig(config):
                    return ancien
            if gestionnaire.storeAuthenticationConfig(config):
                reglages.setValue(cle, config.id())
                return config.id()
        except Exception as e:
            journal.ignorer(e, "magasin d'authentification (base)")
        return ''

    def _relier_bd(self, chemin):
        """Rebranche les couches PostGIS du projet sur la base de l'instance.

        Un projet publie porte l'adresse interne de la base, celle que
        Lizmap emploie depuis le serveur. Ouvert tel quel sur un poste de
        travail, il ne joint rien : QGIS ouvre « Traiter les couches
        inutilisables » et le projet arrive vide.
        """
        if not self.session.is_connected():
            return
        pg = self.session.get_postgis_uri()
        if not (pg.get('host') and pg.get('dbname')):
            return
        authcfg = self._authcfg_bd(pg)
        try:
            compte = liaison_bd.relier(chemin, pg, authcfg)
        except Exception as e:
            self._log(tr('Couches PostGIS non rebranchées : {}').format(e), 'warn')
            return
        if not compte:
            return
        if authcfg:
            self._log(
                tr('{} couche(s) PostGIS rebranchée(s) sur la base de '
                "l'instance.").format(compte), 'ok')
        else:
            self._log(
                tr('{} couche(s) PostGIS rebranchée(s), mais le magasin '
                "d'authentification de QGIS est indisponible : le mot de "
                'passe de la base est écrit en clair dans le projet.').format(compte),
                'warn')

    def _on_project_downloaded(self, local_path):
        self._sync_open_button()
        self._log(tr('Téléchargé → {0}', local_path), 'ok')
        item = self.tree.currentItem()
        self._open_project_api_path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self._relier_bd(local_path)
        ok = QgsProject.instance().read(local_path)
        if ok:
            fname = os.path.basename(local_path)
            self._log(tr('Projet ouvert : {0}', fname), 'ok')
            # Pré-remplir la section Publication
            self.lbl_local_project.setText(fname)
            self.lbl_local_project.setStyleSheet(
                f'font-size: 13px; color: {_C_SUCCESS_TX}; font-weight: 600;'
            )
            if self._open_project_api_path:
                self.txt_publish_dest.setText(self._open_project_api_path)
        else:
            self._log(tr('Impossible d\'ouvrir le projet dans QGIS.'), 'error')

    def _sync_publish_button(self):
        """N'active « Publier » que si la publication peut aboutir.

        Le bouton restait vert et cliquable sans projet ouvert : on ne
        l'apprenait qu'apres coup, par un message dans la console.
        """
        projet_ouvert = bool(QgsProject.instance().fileName())
        connecte      = self.session.is_connected()
        destination   = bool(self.txt_publish_dest.text().strip())

        # Un espace partage en lecture seule prime sur tout le reste :
        # les fonctions de synchronisation ne doivent pas le contredire.
        # La validation n'ecrit rien : elle reste permise meme en lecture
        # seule, et n'exige pas de destination.
        self.btn_valider.setEnabled(projet_ouvert and connecte)
        self.btn_valider.setToolTip(
            tr('Fait examiner le projet par le serveur sans rien publier.')
            if (projet_ouvert and connecte) else
            (tr("Connectez-vous d'abord a une instance") if not connecte
             else tr('Ouvrez un projet dans QGIS (Ctrl+O)'))
        )

        if self._lecture_seule or self._jeton_lecture:
            self.btn_publish.setEnabled(False)
            self.btn_publish.setToolTip(
                tr('Lecture seule : cet espace ne vous accorde pas la '
                'gestion des fichiers.')
            )
            return

        self.btn_publish.setEnabled(projet_ouvert and connecte and destination)
        if not connecte:
            raison = tr("Connectez-vous d'abord à une instance")
        elif not projet_ouvert:
            raison = tr('Ouvrez un projet dans QGIS (Ctrl+O) ou enregistrez-en un (Ctrl+S)')
        elif not destination:
            raison = tr('Sélectionnez un fichier dans la liste pour fixer la destination')
        else:
            raison = (tr('Sauvegarde le projet QGIS actif et le publie sur le serveur.\n'
                      'Lizmap recharge automatiquement.'))
        self.btn_publish.setToolTip(raison)

    def _on_qgis_project_changed(self):
        """Suit l'ouverture, la fermeture et le renommage du projet QGIS."""
        project    = QgsProject.instance()
        local_path = project.fileName()
        if not local_path:
            self.lbl_local_project.setText(tr('Aucun projet ouvert dans QGIS'))
            self.lbl_local_project.setStyleSheet(
                f'font-size: 13px; color: {_C_MUTED}; font-style: italic;'
            )
            self._sync_publish_button()
            return
        fname = os.path.basename(local_path)
        self.lbl_local_project.setText(fname)
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_TEXT}; font-style: normal;'
        )
        # Auto-suggestion de destination si champ vide
        if not self.txt_publish_dest.text():
            self._suggerer_destination()
        self._sync_publish_button()

    def _check_quota_block(self, action=None):
        """Retourne True (et log) si l'instance est suspendue pour quota."""
        action = action or tr('cette action')
        if getattr(self, '_quota_suspended', False):
            self._log(
                tr("Impossible : {0}.\nVotre instance est suspendue pour dépassement de quota.\nSupprimez des fichiers ou des données pour libérer de l'espace.", action),
                'error',
            )
            return True
        return False

    # ══════════════════════════════════════════════════════════════════
    # Validation d'un projet
    # ══════════════════════════════════════════════════════════════════

    _GRAVITES = (
        ('bloquant',  tr('Bloquant'),  '#B91C1C'),
        ('important', tr('Important'), '#B45309'),
        ('remarque',  tr('Remarque'),  _C_MUTED),
    )

    def _valider_selection(self):
        """Valide le projet selectionne dans l'arbre, la ou il est."""
        item = self.tree.currentItem()
        if not item:
            return
        chemin = item.data(0, Qt.ItemDataRole.UserRole) or ''
        if chemin.lower().endswith('.qgz'):
            self._log(
                tr('Le validateur du serveur attend un projet .qgs. '
                'Ouvrez ce projet, puis validez-le depuis QGIS.'), 'warn')
            return
        self._do_valider_projet(
            file_id=item.data(0, Qt.ItemDataRole.UserRole + 1),
            nom=os.path.basename(chemin))

    def _do_valider_projet(self, file_id=None, nom=None):
        """Fait examiner un projet par le serveur, sans rien publier.

        Le televersement previent deja des defauts qu'il rencontre, mais il
        le fait au moment ou le projet part en ligne — trop tard pour y
        renoncer. Ici, rien n'est ecrit ni publie : le serveur lit le
        fichier en memoire et rend l'etat des lieux.
        """
        if not self.session.is_connected():
            self._log(tr("Connectez-vous d'abord a une instance."), 'warn')
            return

        chemin_local = None
        self._rapport_local = file_id is None
        if file_id is None:
            projet = QgsProject.instance()
            chemin_local = projet.fileName()
            if not chemin_local:
                self._log(
                    tr('Aucun projet QGIS ouvert. Ouvrez un projet (Ctrl+O), ou '
                    'selectionnez-en un dans la liste, clic droit, '
                    'Valider le projet.'), 'warn')
                return
            # Valider ce qui est a l'ecran, pas ce qui reste sur le disque.
            if not projet.write():
                self._log(tr('Echec de la sauvegarde locale du projet.'), 'error')
                return
            nom = os.path.basename(chemin_local)

        self.btn_valider.setEnabled(False)
        self._log(tr('Validation de {}...').format(nom))
        self._start_loading(tr('Validation de {}...').format(nom))
        self._val_worker = ValidationWorker(self.session, chemin_local, file_id)
        self._val_worker.finished.connect(self._on_rapport_validation)
        self._val_worker.error.connect(
            lambda e: (self._log(tr('Validation : {}').format(e), 'error'),
                       self._sync_publish_button())
        )
        self._val_worker.finished.connect(lambda _: self._stop_loading())
        self._val_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._val_worker)
        self._val_worker.start()

    def _on_rapport_validation(self, rapport):
        self._sync_publish_button()
        resume = rapport.get('resume') or {}
        conforme = rapport.get('connexions_conformes', True)

        if not sum(resume.values()) and conforme:
            self._log(tr('Projet valide : aucun signalement.'), 'ok')
        else:
            self._log(
                tr('Validation : {} bloquant(s), {} important(s), {} remarque(s).')
                .format(resume.get('bloquant', 0), resume.get('important', 0),
                        resume.get('remarque', 0)),
                'error' if (resume.get('bloquant') or not conforme) else 'warn',
                deployer=False)
        self._afficher_rapport(rapport)

    def _afficher_rapport(self, rapport):
        """Remplit le panneau de validation, classe par gravite."""
        resume = rapport.get('resume') or {}
        erreurs = rapport.get('erreurs_connexion') or []

        if erreurs:
            self.lbl_validation.setText(
                '<b style="color:#B91C1C;">' + tr('Les connexions PostgreSQL ne sont '
                'pas conformes : la publication sera refusée.') + '</b><br>'
                + '<br>'.join(str(e) for e in erreurs))
        elif not sum(resume.values()):
            self.lbl_validation.setText(
                tr('<b style="color:{};">Aucun signalement.</b> Le projet peut '
                'être publié.').format(_C_SUCCESS_TX))
        else:
            self.lbl_validation.setText(
                tr('Deux règles seules font refuser le dépôt : des couches en '
                '<b>projections mélangées</b>, et des <b>connexions '
                "PostgreSQL</b> étrangères à l'instance. Les autres "
                'signalements dégradent la carte sans interdire la publication.'))

        self.lst_validation.clear()
        self.txt_validation.clear()

        par_gravite = {}
        for signalement in rapport.get('signalements') or []:
            par_gravite.setdefault(
                signalement.get('severite'), []).append(signalement)

        for cle, libelle, couleur in self._GRAVITES:
            lot = par_gravite.get(cle) or []
            if not lot:
                continue
            parent = QTreeWidgetItem(
                self.lst_validation, ['{} ({})'.format(libelle, len(lot)), '', ''])
            parent.setForeground(0, QColor(couleur))
            police = parent.font(0)
            police.setBold(True)
            parent.setFont(0, police)
            for signalement in lot:
                enfant = QTreeWidgetItem(parent, [
                    signalement.get('couche') or '·',
                    signalement.get('categorie') or '',
                    signalement.get('constat') or '',
                ])
                enfant.setData(0, Qt.ItemDataRole.UserRole, signalement)
            parent.setExpanded(True)

        # Sans signalement, la table n'a rien a montrer : la ligne d'en-tete
        # suffit, et le panneau reste court.
        vide = not sum(resume.values())
        self._sync_bouton_corriger(vide)
        self.lst_validation.setVisible(not vide)
        self.txt_validation.setVisible(not vide)

        self.lst_validation.resizeColumnToContents(0)
        self.lst_validation.resizeColumnToContents(1)
        # Le rapport est demande : on va le montrer, pas l'attendre.
        self.tabs.setCurrentIndex(1)
        self.sous_onglets.setCurrentIndex(1)

    def _sync_bouton_corriger(self, rapport_vide=False):
        """« Corriger dans QGIS » : seulement pour le projet ouvert, et s'il
        y a quelque chose que le plugin sait corriger."""
        from . import corrections
        montrer = False
        if getattr(self, '_rapport_local', False) and not rapport_vide:
            try:
                montrer = bool(corrections.plan(QgsProject.instance()))
            except Exception as e:  # noqa: BLE001
                journal.ignorer(e, 'plan des corrections')
        self.btn_corriger.setVisible(montrer)

    def _corriger_dans_qgis(self):
        """Propose les corrections possibles, les applique, enregistre le
        projet et relance la validation."""
        from . import corrections
        projet = QgsProject.instance()
        lot = corrections.plan(projet)
        if not lot:
            self._log(tr('Rien que le plugin sache corriger dans ce projet.'), 'info')
            self.btn_corriger.setVisible(False)
            return
        texte = tr('Le plugin va faire ces corrections dans le projet ouvert :') + '\n\n'
        texte += '\n'.join('· ' + c.description for c in lot)
        if any(c.modifie_donnees for c in lot):
            texte += '\n\n' + tr('Certaines modifient les données (fichiers ou tables '
                                   'de la base), pas seulement le projet.')
        texte += '\n\n' + tr('Le projet est ensuite enregistré, puis validé de nouveau. Continuer ?')
        rep = QMessageBox.question(self, tr('Corriger dans QGIS'), texte)
        if rep != QMessageBox.StandardButton.Yes:
            return
        self._start_loading(tr('Correction du projet…'))
        faites = 0
        try:
            for c in lot:
                try:
                    c.appliquer()
                    faites += 1
                    self._log('✓ ' + c.description, 'success')
                except Exception as e:  # noqa: BLE001
                    self._log(tr('Échec : {0} ({1})', c.description, e), 'error')
            if not projet.write():
                self._log(tr('Echec de la sauvegarde locale du projet.'), 'error')
                return
        finally:
            self._stop_loading()
        self._log(tr('{0} correction(s) sur {1} appliquée(s).', faites, len(lot)),
                  'success' if faites == len(lot) else 'warn')
        self._do_valider_projet()

    def _montrer_signalement(self):
        """Detaille le signalement choisi dans le panneau."""
        item = self.lst_validation.currentItem()
        donnees = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not donnees:
            self.txt_validation.clear()
            return
        self.txt_validation.setPlainText(
            tr('{}\n\nConséquence : {}\n\nSolution : {}').format(
                donnees.get('constat', ''),
                donnees.get('consequence', '') or '·',
                donnees.get('solution', '') or '·'))

    def _verifier_projections_avant_publication(self):
        """Propose de ramener les couches dans une projection unique.

        Le serveur refuse un projet dont les couches ne partagent pas le meme
        systeme de coordonnees. Le decouvrir apres coup, par un message de
        refus, obligerait l'utilisateur a tout reprendre a la main dans QGIS :
        autant le lui proposer ici, ou la reprojection est possible.

        Rend True si la publication peut se poursuivre.
        """
        from . import reprojection

        projet = QgsProject.instance()
        try:
            cible, divergentes, en_base = reprojection.couches_a_reprojeter(projet)
        except Exception as e:  # noqa: BLE001
            journal.ignorer(e, 'controle des projections avant publication')
            return True          # ne jamais bloquer sur le controle lui-meme

        # Une table PostGIS se reprojette en base, pas en l'exportant vers un
        # fichier : le plugin le dit, et laisse la main.
        if en_base:
            noms_base = ', '.join(f'« {c.name()} »' for c in en_base)
            self._log(
                tr('{0} couche(s) PostGIS ne sont pas en {1} : {2}. Reprojetez-les dans la base (le rapport de validation donne la commande), puis republiez.', len(en_base), cible, noms_base), 'warn')
            return False

        if not divergentes:
            return True

        noms = ', '.join(f'« {c.name()} »' for c in divergentes[:4])
        if len(divergentes) > 4:
            noms += tr(' et {0} autre(s)', len(divergentes) - 4)

        reponse = QMessageBox.question(
            self,
            tr('Projections différentes'),
            tr('{0} couche(s) ne sont pas dans le systeme de coordonnees {1} : {2}.\n\nLe serveur refusera ce projet : chaque couche divergente serait reprojetee a chaque affichage, pour chaque visiteur de la carte.\n\nReprojeter ces couches en {3} maintenant ?\nLe projet et ses fichiers de donnees sont modifies sur place ; une sauvegarde « .bak » de chacun est posee a cote.', len(divergentes), cible, noms, cible),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reponse != QMessageBox.StandardButton.Yes:
            self._log(
                tr('Publication annulée : les couches doivent partager le même '
                'système de coordonnées.'), 'warn')
            return False

        self._start_loading(tr('Reprojection des couches…'))
        try:
            reussies, echouees = reprojection.uniformiser(
                projet, cible, divergentes,
                journal_avancement=lambda m: self._log(m),
            )
        finally:
            self._stop_loading()

        for nom, motif in echouees:
            self._log(tr("« {0} » n'a pas pu être reprojetée : {1}", nom, motif), "error")
        if echouees:
            self._log(
                tr('Publication interrompue. Une sauvegarde « .bak » a été '
                'posée à côté de chaque fichier touché.'), 'warn')
            return False

        self._log(
            tr('{0} couche(s) reprojetée(s) en {1}. Le projet a été enregistré sous son nom ; une sauvegarde « .qgs.bak » est disponible en cas de besoin.', len(reussies), cible), 'success')
        return True

    # Cout d'une mise en page GARNIE a la lecture du projet par QGIS Server,
    # en secondes, et delai au dela duquel le serveur abandonne. Mesures sur
    # une instance reelle : sept mises en page = plus de 30 s et le processus
    # tue, les memes sept VIDES = 1 s. Ces valeurs sont celles du validateur
    # cote serveur (qgs_validator.COUT_MISE_EN_PAGE_S / DELAI_SERVEUR_S) : si
    # l'une bouge, l'autre doit suivre.
    COUT_MISE_EN_PAGE_S = 5.0
    DELAI_SERVEUR_S = 30
    SEUIL_MISES_EN_PAGE_ALERTE = 3

    def _verifier_mises_en_page_avant_publication(self):
        """Avertit quand les mises en page empechent le projet de se charger.

        QGIS Server relit toutes les mises en page a l'ouverture du projet,
        avant de dessiner quoi que ce soit ; chacune coute quelques secondes,
        et le total se compare au delai du serveur. Passe ce delai, la carte
        repond une erreur a chaque demarrage a froid, sans qu'aucune couche
        soit en cause — un defaut invisible ici, ou QGIS garde le projet
        ouvert et ne paie cette lecture qu'une fois.

        Seules les mises en page GARNIES comptent : une mise en page vide ne
        coute rien, c'est ce qu'elle contient qui se paie.

        Le plugin ne supprime rien : une mise en page represente du travail,
        et le choix de celle a garder n'appartient qu'a son auteur. Il
        avertit, et laisse decider.

        Rend True si la publication peut se poursuivre.
        """
        try:
            projet = QgsProject.instance()
            garnies = []
            for mep in projet.layoutManager().printLayouts():
                # `items()` compte aussi la page elle-meme et les reperes ;
                # seuls les elements poses par l'auteur nous interessent.
                elements = [e for e in mep.items()
                            if getattr(e, 'type', None) and e.type() >= 65638]
                if elements:
                    garnies.append((mep.name(), len(elements)))
        except Exception as e:  # noqa: BLE001
            journal.ignorer(e, 'controle des mises en page avant publication')
            return True          # ne jamais bloquer sur le controle lui-meme

        if len(garnies) < self.SEUIL_MISES_EN_PAGE_ALERTE:
            return True

        cout = len(garnies) * self.COUT_MISE_EN_PAGE_S
        noms = ', '.join('« {} »'.format(nom) for nom, _ in garnies[:4])
        if len(garnies) > 4:
            noms += tr(' et {} autre(s)').format(len(garnies) - 4)

        if cout >= self.DELAI_SERVEUR_S:
            gravite = (tr('Le serveur ne pourra PAS ouvrir ce projet : il '
                       'abandonne au bout de {} secondes.')
                       .format(self.DELAI_SERVEUR_S))
        else:
            gravite = (tr('La marge est mince : le moindre ralentissement fera '
                       'basculer la carte en erreur.'))

        reponse = QMessageBox.question(
            self,
            tr('Mises en page nombreuses'),
            tr('Ce projet contient {} mises en page : {}.\n\n'
            'Le serveur les relit toutes à chaque ouverture du projet, avant '
            "d'afficher la moindre couche : comptez environ {:.0f} secondes. "
            '{}\n\n'
            "Ne gardez qu'une ou deux mises en page dans le projet publié. "
            "Les autres formats restent accessibles à l'impression en "
            'changeant le format de sortie : vous ne perdez que les gabarits '
            'enregistrés.\n\n'
            'Publier quand même ?').format(len(garnies), noms, cout, gravite),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reponse != QMessageBox.StandardButton.Yes:
            self._log(
                tr('Publication annulée. Supprimez les mises en page inutiles '
                '(Projet ▸ Gestionnaire de mises en page), enregistrez, puis '
                'republiez.'), 'warn')
            return False

        self._log(
            tr('{} mises en page conservées : le chargement de la carte prendra '
            'environ {:.0f} secondes.').format(len(garnies), cout), 'warn')
        return True

    def _do_publish_project(self):
        """
        Publie le projet QGIS actif vers le serveur Lizmap.
        Scénarios couverts :
          A) Projet ouvert depuis le serveur via le plugin → destination pré-remplie
          B) Projet ouvert localement → l'utilisateur indique la destination
          C) Nouveau projet QGIS → l'utilisateur choisit destination et sauvegarde d'abord
        """
        if self._check_quota_block('publication'):
            return
        if not self.session.is_connected():
            self._log(tr('Connectez-vous d\'abord à une instance.'), 'warn')
            return

        project    = QgsProject.instance()
        local_path = project.fileName()
        if not local_path:
            self._log(
                tr('Aucun projet QGIS ouvert. '
                'Ouvrez un projet (Ctrl+O) ou créez-en un et sauvegardez-le (Ctrl+S).'),
                'warn',
            )
            return

        # Avant tout envoi : le projet doit pouvoir etre accepte.
        if not self._verifier_projections_avant_publication():
            return
        if not self._verifier_mises_en_page_avant_publication():
            return
        # Le projet a pu etre reenregistre par la reprojection : on relit son
        # chemin plutot que de se fier a celui d'avant.
        local_path = project.fileName() or local_path

        dest_path = self.txt_publish_dest.text().strip()
        if not dest_path:
            self._log(
                tr('Indiquez le chemin de destination sur le serveur.\nEx: /qgis/mon-projet.qgs, ou sélectionnez un fichier dans la liste.'),
                'warn',
            )
            return

        # Normaliser : si dest est un dossier, ajouter le nom du fichier
        if not dest_path.lower().endswith(('.qgs', '.qgz')):
            dest_path = dest_path.rstrip('/') + '/' + os.path.basename(local_path)
            self.txt_publish_dest.setText(dest_path)

        # Sauvegarder automatiquement le projet QGIS
        if not project.write():
            self._log(tr('Échec de la sauvegarde locale du projet.'), 'error')
            return

        self._log(tr('Publication → {0}…', dest_path))
        self.btn_publish.setEnabled(False)
        self._save_worker = SaveSymbologyWorker(self.session, local_path, dest_path)
        self._save_worker.finished.connect(self._on_published)
        self._save_worker.status.connect(lambda msg: self._log(msg))
        self._save_worker.error.connect(
            lambda e: (self._log(e, 'error'), self.btn_publish.setEnabled(True))
        )
        self._start_loading(tr('Publication vers Lizmap…'))
        self._save_worker.finished.connect(lambda: self._stop_loading())
        self._save_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._save_worker)
        self._save_worker.start()

    def _on_published(self):
        self.btn_publish.setEnabled(True)
        self._log(tr('Projet publié : Lizmap recharge automatiquement.'), 'ok')
        self._load_files()  # rafraîchir l'arbre

    def _sync_open_button(self):
        """N'active « Ouvrir » que pour un vrai projet QGIS.

        Le bouton restait cliquable sur un dossier ou un shapefile, et
        l'utilisateur ne decouvrait son erreur qu'apres coup, par un
        message dans la console.
        """
        item = self.tree.currentItem()
        chemin = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        dossier = item.data(0, Qt.ItemDataRole.UserRole + 2) if item else False
        projet = bool(
            chemin and not dossier and chemin.lower().endswith(('.qgs', '.qgz'))
        ) and not self._lecture_seule
        if projet and getattr(self.session, 'est_protege', lambda _c: False)(chemin):
            projet = False
            self.btn_open.setEnabled(False)
            self.btn_open.setToolTip(tr('Projets protégés sur cette instance : ouverture désactivée.'))
            return
        self.btn_open.setEnabled(projet)
        self.btn_open.setToolTip(
            tr('Ouvrir le projet .qgs/.qgz sélectionné dans QGIS') if projet
            else tr('Sélectionnez un fichier .qgs ou .qgz')
        )

    def _on_file_click(self, item, _col):
        """Clic simple : pré-remplir le champ Destination dans la section Publication."""
        api_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir   = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if api_path and not is_dir:
            self.txt_publish_dest.setText(api_path)
            # Choix explicite : la navigation ne doit plus le remplacer.
            self._dest_choisie = True

    def _on_file_dblclick(self, item, _col):
        api_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir   = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if is_dir:
            self._path_history.append(self._current_path)
            self._current_path = api_path
            self._entrer_dans_dossier()
            self.tree.clear()           # feedback immédiat
            self.lbl_path.setText(api_path)
            self._load_files()
        elif api_path and api_path.lower().endswith(('.qgz', '.qgs')):
            self._do_open_project()

    def _entrer_dans_dossier(self):
        """Change de dossier : la destination redevient une suggestion."""
        self._dest_choisie = False

    # ══════════════════════════════════════════════════════════════════
    # Actions — Gestion fichiers (nouveau dossier, supprimer, renommer, upload ici)
    # ══════════════════════════════════════════════════════════════════

    def _show_context_menu(self, pos):
        """Menu clic-droit sur l'arbre."""
        items = self.tree.selectedItems()
        menu  = QMenu(self)

        if items:
            is_dir  = items[0].data(0, Qt.ItemDataRole.UserRole + 2)
            is_proj = (not is_dir and
                       (items[0].data(0, Qt.ItemDataRole.UserRole) or '').lower().endswith(('.qgs', '.qgz')))

            if is_proj and len(items) == 1:
                act_open = menu.addAction(_icon('download', 'white', 14), tr('Ouvrir dans QGIS'))
                act_open.triggered.connect(self._do_open_project)
                act_open.setEnabled(not getattr(self.session, 'est_protege', lambda _c: False)(
                    items[0].data(0, Qt.ItemDataRole.UserRole + 1) or ''))
                act_val = menu.addAction(
                    _icon('check-circle', _C_PRIMARY, 14), tr('Valider le projet'))
                act_val.triggered.connect(self._valider_selection)
                menu.addSeparator()

            if len(items) == 1:
                act_rename = menu.addAction(_icon('edit-2', _C_MUTED, 14), tr('Renommer'))
                act_rename.triggered.connect(self._do_rename_selected)

            lbl_copy = tr('Copier ({0})', len(items)) if len(items) > 1 else tr('Copier')
            act_copy = menu.addAction(_icon('copy', _C_MUTED, 14), lbl_copy)
            act_copy.triggered.connect(self._do_copy)

            lbl_cut = tr('Couper ({0})', len(items)) if len(items) > 1 else tr('Couper')
            act_cut = menu.addAction(_icon('scissors', _C_MUTED, 14), lbl_cut)
            act_cut.triggered.connect(self._do_cut)

            lbl_del = tr('Supprimer ({0})', len(items)) if len(items) > 1 else tr('Supprimer')
            act_del = menu.addAction(_icon('trash-2', '#e74c3c', 14), lbl_del)
            act_del.triggered.connect(self._do_delete_selected)
            menu.addSeparator()

        if getattr(self, '_clipboard_ids', None):
            mode = tr('Coller') if self._clipboard_mode == 'copy' else tr('Déplacer ici')
            count = len(self._clipboard_ids)
            act_paste = menu.addAction(
                _icon('clipboard', _C_SUCCESS_TX, 14),
                tr('{0} ({1} élément(s))', mode, count),
            )
            act_paste.triggered.connect(self._do_paste)
            menu.addSeparator()

        act_mkdir = menu.addAction(_icon('folder-plus', _C_MUTED, 14), tr('Nouveau dossier ici'))
        act_mkdir.triggered.connect(self._do_create_folder)
        act_up = menu.addAction(_icon('upload', _C_MUTED, 14), tr('Uploader des fichiers ici'))
        act_up.triggered.connect(self._do_upload_here)
        act_up_dir = menu.addAction(_icon('folder-upload', _C_PRIMARY, 14), tr('Uploader un dossier ici'))
        act_up_dir.triggered.connect(self._do_upload_folder_here)

        if self._jeton_lecture:
            for act in menu.actions():
                if not act.isSeparator() and act.text() not in (tr('Ouvrir dans QGIS'), tr('Valider le projet')):
                    act.setEnabled(False)

        # exec() et non exec_() : Qt6 supprime l'alias historique, ajoute
        # en Python 2 quand « exec » etait un mot reserve.
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _selected_ids(self):
        """Retourne la liste des IDs des items sélectionnés."""
        return [
            item.data(0, Qt.ItemDataRole.UserRole + 1)
            for item in self.tree.selectedItems()
            if item.data(0, Qt.ItemDataRole.UserRole + 1) is not None
        ]

    # ── Copier / Couper / Coller ──────────────────────────────────────

    def _do_copy(self):
        ids = self._selected_ids()
        if not ids:
            self._log(tr('Sélectionnez au moins un élément à copier.'), 'warn')
            return
        self._clipboard_ids = ids
        self._clipboard_mode = 'copy'
        names = [it.text(0) for it in self.tree.selectedItems()]
        self._log(tr('{0} élément(s) copié(s) : {1}', len(ids), ", ".join(names)))

    def _do_cut(self):
        ids = self._selected_ids()
        if not ids:
            self._log(tr('Sélectionnez au moins un élément à couper.'), 'warn')
            return
        self._clipboard_ids = ids
        self._clipboard_mode = 'cut'
        names = [it.text(0) for it in self.tree.selectedItems()]
        self._log(tr('{0} élément(s) coupé(s) : {1}', len(ids), ", ".join(names)))

    def _do_paste(self):
        if self._refus_jeton_lecture():
            return
        ids = getattr(self, '_clipboard_ids', None)
        if not ids:
            self._log(tr('Rien à coller. Copiez ou coupez d\'abord un élément.'), 'warn')
            return
        if not self.session.is_connected():
            return
        mode = getattr(self, '_clipboard_mode', 'copy')
        dest = self._current_path
        count = len(ids)

        if mode == 'copy':
            if self._check_quota_block('copie'):
                return
            self._start_loading(tr('Copie de {0} élément(s)…', count))
            try:
                self.session.copy_files(ids, dest)
                self._stop_loading()
                self._log(tr('{0} élément(s) collé(s) dans {1}', count, dest), 'ok')
            except Exception as e:
                self._stop_loading()
                self._log(tr('Erreur copie : {0}', e), 'error')
        else:
            self._start_loading(tr('Déplacement de {0} élément(s)…', count))
            try:
                self.session.move_files(ids, dest)
                self._stop_loading()
                self._log(tr('{0} élément(s) déplacé(s) vers {1}', count, dest), 'ok')
                self._clipboard_ids = None  # couper = one-shot
            except Exception as e:
                self._stop_loading()
                self._log(tr('Erreur déplacement : {0}', e), 'error')

        self._load_files()

    def _do_create_folder(self):
        if self._refus_jeton_lecture():
            return
        if self._check_quota_block(tr('création de dossier')):
            return
        if not self.session.is_connected():
            return
        name, ok = QInputDialog.getText(self, tr('Nouveau dossier'), tr('Nom du dossier :'))
        if not ok or not name.strip():
            return
        name = name.strip()
        self._start_loading(tr('Création de "{0}"…', name))
        self._mkdir_worker = CreateFolderWorker(self.session, name, self._current_path)
        self._mkdir_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                     self._log(tr('Dossier "{0}" créé.', name), 'ok')))
        self._mkdir_worker.error.connect(lambda e: (self._stop_loading(),
                                                    self._log(tr('Erreur : {0}', e), 'error')))
        self._suivre(self._mkdir_worker)
        self._mkdir_worker.start()

    def _do_delete_selected(self):
        if self._refus_jeton_lecture():
            return
        ids = self._selected_ids()
        if not ids:
            self._log(tr('Aucun élément sélectionné.'), 'warn')
            return
        names = [item.text(0) for item in self.tree.selectedItems()]
        preview = ', '.join(names[:3]) + (f' … +{len(names)-3}' if len(names) > 3 else '')
        rep = QMessageBox.question(
            self, tr('Confirmer la suppression'),
            tr('Supprimer {0} élément(s) ?\n{1}', len(ids), preview),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if rep != QMessageBox.StandardButton.Yes:
            return
        self._start_loading(tr('Suppression de {0} élément(s)…', len(ids)))
        self._del_worker = DeleteWorker(self.session, ids)
        self._del_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                   self._log(tr('{0} élément(s) supprimé(s).', len(ids)), 'ok')))
        self._del_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(tr('Erreur suppression : {0}', e), 'error')))
        self._suivre(self._del_worker)
        self._del_worker.start()

    def _do_rename_selected(self):
        if self._refus_jeton_lecture():
            return
        items = self.tree.selectedItems()
        if len(items) != 1:
            self._log(tr('Sélectionnez un seul élément pour le renommer.'), 'warn')
            return
        item    = items[0]
        file_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        old     = item.text(0)
        new_name, ok = QInputDialog.getText(self, tr('Renommer'), tr('Nouveau nom :'), text=old)
        if not ok or not new_name.strip() or new_name.strip() == old:
            return
        new_name = new_name.strip()
        self._start_loading(tr('Renommage vers "{0}"…', new_name))
        self._ren_worker = RenameWorker(self.session, file_id, new_name)
        self._ren_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                   self._log(tr('"{0}" renommé en "{1}".', old, new_name), 'ok')))
        self._ren_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(tr('Erreur renommage : {0}', e), 'error')))
        self._suivre(self._ren_worker)
        self._ren_worker.start()

    def _do_upload_here(self):
        """Upload un ou plusieurs fichiers dans le dossier courant."""
        if self._refus_jeton_lecture():
            return
        if self._check_quota_block(tr('upload de fichiers')):
            return
        if not self.session.is_connected():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr('Uploader vers {0}', self._current_path),
            self._repertoire_travail(), tr('Tous les fichiers (*.*)')
        )
        if not paths:
            return
        self._definir_repertoire_travail(os.path.dirname(paths[0]))
        self._start_loading(tr('Upload de {0} fichier(s)…', len(paths)))
        self._upf_worker = UploadFilesWorker(self.session, paths, self._current_path)
        self._upf_worker.progress.connect(
            lambda cur, tot, fname: self._log(tr('  [{0}/{1}] {2}…', cur, tot, fname))
        )
        self._upf_worker.finished.connect(lambda n: (self._stop_loading(), self._load_files(),
                                                     self._log(tr('{0} fichier(s) uploadé(s).', n), 'ok')))
        self._upf_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(tr('Erreur upload : {0}', e), 'error')))
        self._suivre(self._upf_worker)
        self._upf_worker.start()

    def _do_upload_folder_here(self):
        """Upload un dossier entier dans le dossier courant via batch."""
        if self._refus_jeton_lecture():
            return
        if self._check_quota_block(tr('upload de dossier')):
            return
        if not self.session.is_connected():
            return
        folder = QFileDialog.getExistingDirectory(
            self, tr('Uploader un dossier vers {0}', self._current_path),
            self._repertoire_travail(),
        )
        if not folder:
            return
        self._definir_repertoire_travail(folder)
        # Collecter tous les fichiers
        entries = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                if fname.startswith('.'):
                    continue
                local = os.path.join(root, fname)
                entries.append(local)
        if not entries:
            self._log(tr('Le dossier est vide.'), 'warn')
            return
        folder_name = os.path.basename(folder)
        self._log(tr('Upload du dossier « {0} » ({1} fichier(s))…', folder_name, len(entries)))
        self._start_loading(tr('Upload de {0} fichier(s)…', len(entries)))
        self._updir_worker = UploadFolderWorker(self.session, folder, self._current_path)
        self._updir_worker.progress.connect(
            lambda cur, tot, fname: self._log(tr('  [{0}/{1}] {2}…', cur, tot, fname))
        )
        self._updir_worker.finished.connect(lambda n: (self._stop_loading(), self._load_files(),
                                                       self._log(tr('{0} fichier(s) uploadé(s).', n), 'ok')))
        self._updir_worker.error.connect(lambda e: (self._stop_loading(),
                                                    self._log(tr('Erreur upload : {0}', e), 'error')))
        self._suivre(self._updir_worker)
        self._updir_worker.start()

    # ══════════════════════════════════════════════════════════════════
    # Actions — Upload dossier (onglet Upload)
    # ══════════════════════════════════════════════════════════════════

    def _do_upload_folder(self):
        if self._check_quota_block(tr('upload de dossier')):
            return
        local  = self.txt_local.text()
        remote = self.txt_remote.text().strip() or '/'
        if not local or not os.path.isdir(local):
            self._log(tr('Sélectionnez un dossier local valide.'), 'warn')
            return
        if not self.session.is_connected():
            self._log(tr('Non connecté.'), 'warn')
            return
        self.btn_upload.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._log(tr('Upload : {0}  →  {1}…', local, remote))
        self._up_worker = UploadFolderWorker(self.session, local, remote)
        self._up_worker.progress.connect(self._on_upload_progress)
        self._up_worker.finished.connect(self._on_upload_done)
        self._up_worker.error.connect(
            lambda e: (
                self._log(e, 'error'),
                self.btn_upload.setEnabled(True),
                self.progress.setVisible(False),
            )
        )
        self._start_loading(tr('Upload en cours…'))
        self._up_worker.finished.connect(lambda _: self._stop_loading())
        self._up_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._up_worker)
        self._up_worker.start()

    def _on_upload_progress(self, cur, tot, fname):
        self.progress.setMaximum(tot)
        self.progress.setValue(cur)
        self.lbl_progress.setText(tr('{0}  ({1} / {2})', fname, cur, tot))

    def _on_upload_done(self, count):
        self.btn_upload.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_progress.setText('')
        self._log(tr('{0} fichier(s) uploadé(s).', count), 'ok')
        self._load_files()

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, tr('Sélectionner un dossier'), self._repertoire_travail(),
        )
        if path:
            self.txt_local.setText(path)
            self._definir_repertoire_travail(path)
            self.txt_remote.setText('/')

    # ══════════════════════════════════════════════════════════════════
    # Actions — PostGIS
    # ══════════════════════════════════════════════════════════════════

    def _restaurer_sections_pg(self):
        """Reprend la repartition des sections, ou en propose une.

        Par defaut la liste des tables prend la moitie, le diagnostic un
        tiers, l'import le reste : c'est l'ordre dans lequel on s'en sert.
        """
        enregistre = QSettings().value(_SECTIONS_PG_CLE)
        if isinstance(enregistre, QByteArray) and not enregistre.isEmpty():
            if self.sections_pg.restoreState(enregistre):
                return
        self.sections_pg.setSizes([300, 200, 160])

    def _memoriser_sections_pg(self):
        QSettings().setValue(_SECTIONS_PG_CLE, self.sections_pg.saveState())

    def _postgis_disponible(self):
        """La base de l'instance est-elle joignable avec ce qu'on sait d'elle ?"""
        pg = self.session.get_postgis_uri()
        return all([pg['host'], pg['dbname'], pg['user'], pg['password']])

    def _sync_postgis_etat(self):
        """Accorde l'onglet PostGIS a l'etat reel de la session.

        Le bandeau « PostGIS non disponible » restait affiche apres coup, a
        cote d'un diagnostic reussi : il n'etait leve que par un nouveau
        chargement des tables, dont le bouton venait justement d'etre
        masque. On ne masque plus ce bouton — c'est la seule sortie — et
        l'etat se recalcule a chaque changement de session.
        """
        dispo = self.session.is_connected() and self._postgis_disponible()
        self.pg_unavailable.setVisible(
            self.session.is_connected() and not dispo
        )
        raison = getattr(self.session, 'metadata_error', '')
        if raison:
            r = raison.rstrip('.')
            texte = (tr("La base PostGIS de l'instance ne peut pas être ouverte : {0}.", r[:1].lower() + r[1:]))
            if 'droit' in r:
                texte += tr("\nDemandez ce droit à un administrateur du portail.")
            self.lbl_pg_indispo.setText(texte)
        else:
            self.lbl_pg_indispo.setText(
                tr("PostGIS non disponible pour cette instance.\n"
                "L'instance doit être déployée avec une base de données "
                "PostgreSQL/PostGIS pour utiliser cette fonctionnalité."))
        self.lst_pg.setVisible(dispo)
        self.btn_load_pg.setEnabled(dispo)
        self.btn_diag_pg.setEnabled(dispo)
        # Serveur de son organisation : le portail optimise la base lui-même
        # (Maintenance > Accélérer) ; le bouton ne mènerait qu'à un refus.
        self.btn_diag_pg.setVisible(not getattr(self.session, 'entreprise', False))
        self._sync_pg_buttons()

    def _load_postgis_tables(self):
        """Demande la liste des tables, sans bloquer l'interface."""
        if not self._postgis_disponible():
            self._sync_postgis_etat()
            return
        self._sync_postgis_etat()
        pg = self.session.get_postgis_uri()

        self.btn_load_pg.setEnabled(False)
        self._log(tr('Lecture des tables de la base…'))
        self._start_loading(tr('Lecture des tables…'))
        self._tables_worker = ListerTablesWorker(pg)
        self._tables_worker.finished.connect(
            lambda lignes: self._on_tables_pretes(pg, lignes))
        self._tables_worker.manquant.connect(
            lambda: (self._log(
                tr('psycopg2 non disponible : utilisation du provider QGIS.')),
                self._load_pg_via_qgis(pg))
        )
        self._tables_worker.error.connect(
            lambda e: self._log(tr('Connexion PostGIS échouée : {}').format(e), 'error'))
        for signal in (self._tables_worker.finished,
                       self._tables_worker.error):
            signal.connect(lambda _=None: self._stop_loading())
        self._tables_worker.manquant.connect(lambda: self._stop_loading())
        for signal in (self._tables_worker.finished,
                       self._tables_worker.error,
                       self._tables_worker.manquant):
            signal.connect(lambda *_: self._sync_pg_buttons())
        self._suivre(self._tables_worker)
        self._tables_worker.start()

    def _on_tables_pretes(self, pg, rows):
        """Remplit la liste. Tout ce qui touche a Qt reste dans ce fil-ci."""
        self.lst_pg.clear()
        db_ico = _icon('database', '#8e44ad', 14)
        for table, schema, geom_col, srid in rows:
            # Tables de service de QGIS : ce sont des donnees internes
            # (styles, projets stockes en base), pas des couches a afficher.
            if table in _PG_TABLES_INTERNES:
                continue
            item = QTreeWidgetItem([table, schema, geom_col or '·', str(srid)])
            item.setIcon(0, db_ico)
            item.setData(0, Qt.ItemDataRole.UserRole, {
                **pg, 'table': table, 'schema': schema,
                # Chaine vide = table non spatiale : QGIS la chargera en
                # table attributaire. Y mettre 'geom' par defaut inventerait
                # une colonne inexistante et rendrait la couche invalide.
                'geom_col': geom_col or '',
            })
            self.lst_pg.addTopLevelItem(item)
        self._log(tr('{} table(s) chargée(s).').format(
            self.lst_pg.topLevelItemCount()), 'ok')
        self._sync_pg_buttons()
        self._detect_default_schema(rows)

    def _detect_default_schema(self, rows):
        """Pré-remplit le champ schéma d'import avec le premier schéma utilisateur trouvé.
        Exclut public et lizmap — fallback sur public si rien d'autre."""
        if not rows:
            return
        _SKIP = {'public', 'lizmap', 'pg_catalog', 'information_schema',
                 'topology', 'tiger', 'tiger_data'}
        schemas = set()
        for r in rows:
            s = r[1] if isinstance(r, (list, tuple)) else r
            if s:
                schemas.add(s)
        user_schemas = sorted(schemas - _SKIP)
        self.txt_import_schema.setText(user_schemas[0] if user_schemas else 'public')

    def _load_pg_via_qgis(self, pg):
        try:
            from qgis.core import QgsProviderRegistry, QgsAbstractDatabaseProviderConnection
            md  = QgsProviderRegistry.instance().providerMetadata('postgres')
            uri = QgsDataSourceUri()
            uri.setConnection(pg['host'], pg['port'], pg['dbname'],
                              pg['user'], pg['password'])
            conn = md.createConnection(uri.uri(False), {})
            # Tous les schémas, tous types (tables + vues + vues matérialisées)
            try:
                flags = (
                    QgsAbstractDatabaseProviderConnection.TableFlag.View |
                    QgsAbstractDatabaseProviderConnection.TableFlag.MaterializedView |
                    QgsAbstractDatabaseProviderConnection.TableFlag.Foreign
                )
                tables = conn.tables('', flags)
            except Exception:
                # Fallback : API sans flags
                tables = conn.tables('')
            _EXCLUDED = {'pg_catalog', 'information_schema', 'topology',
                         'tiger', 'tiger_data', 'public', 'lizmap'}
            self.lst_pg.clear()
            db_ico = _icon('database', '#8e44ad', 14)
            for t in tables:
                if (t.schema() or 'public') in _EXCLUDED:
                    continue
                item = QTreeWidgetItem([
                    t.tableName(), t.schema() or 'public',
                    t.geometryColumnName() or '·',
                    str(t.crs().postgisSrid()) if t.crs().isValid() else '·',
                ])
                item.setIcon(0, db_ico)
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    **pg, 'table': t.tableName(),
                    'schema': t.schema() or 'public',
                    'geom_col': t.geometryColumnName() or '',
                })
                self.lst_pg.addTopLevelItem(item)
            self._log(tr('{0} table(s) chargée(s).', self.lst_pg.topLevelItemCount()), 'ok')
            self._sync_pg_buttons()
            # Pré-remplir le schéma d'import
            _SKIP_PG = {'public', 'lizmap', 'pg_catalog', 'information_schema',
                        'topology', 'tiger', 'tiger_data'}
            user_schemas = sorted({
                t.schema() or 'public' for t in tables
                if (t.schema() or 'public') not in _EXCLUDED
            } - _SKIP_PG)
            self.txt_import_schema.setText(user_schemas[0] if user_schemas else 'public')
        except Exception as e:
            self._log(str(e), 'error')

    def _add_postgis_layer(self, item):
        if not item:
            self._log(tr('Sélectionnez une table.'), 'warn')
            return
        info = item.data(0, Qt.ItemDataRole.UserRole)
        if not info:
            return
        uri = QgsDataSourceUri()
        uri.setConnection(info['host'], str(info['port']),
                          info['dbname'], info['user'], info['password'])
        # geom_col vide = table non spatiale (chargée quand même)
        uri.setDataSource(info['schema'], info['table'],
                          info.get('geom_col', ''), '', '')
        layer = QgsVectorLayer(uri.uri(False), info['table'], 'postgres')
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self._log(tr('Couche "{0}" ajoutée.', info["table"]), 'ok')
        else:
            # Ne pas incriminer le reseau a l'aveugle : si d'autres couches
            # viennent d'etre chargees, la connexion fonctionne et le probleme
            # est propre a cette table.
            detail = layer.error().summary() if layer.error().messageList() else ''
            if QgsProject.instance().mapLayers():
                raison = detail or tr('table sans clef primaire exploitable par QGIS')
            else:
                raison = detail or tr('vérifiez que {0}:{1} est accessible',
                                      info["host"], info["port"])
            self._log(tr('Couche "{0}" invalide : {1}.', info["table"], raison), 'error')

    # ══════════════════════════════════════════════════════════════════
    # Actions — Import PostGIS
    # ══════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════
    # Actions — Santé de la base
    # ══════════════════════════════════════════════════════════════════

    _COULEURS_GRAVITE = {
        'grave':  (_C_ERROR,   tr('Critique')),
        'moyen':  (_C_WARN,    tr('À traiter')),
        'mineur': (_C_MUTED,   tr('Mineur')),
    }

    def _sync_pg_buttons(self):
        """N'active les actions PostGIS que quand elles peuvent aboutir.

        Meme principe que pour « Ouvrir » et « Publier » : un bouton vert
        et cliquable qui repond par un message d'erreur fait perdre du
        temps a chaque fois.
        """
        table = self.lst_pg.currentItem() is not None
        self.btn_add_pg.setEnabled(table)
        self.btn_add_pg.setToolTip(
            tr('Ajouter la table sélectionnée comme couche') if table
            else tr('Sélectionnez une table dans la liste')
        )

        if not hasattr(self, 'btn_import_pg'):
            return
        couche  = self.cmb_import_layer.currentIndex() >= 0
        schema  = bool(self.txt_import_schema.text().strip())
        cible   = bool(self.txt_import_table.text().strip())
        if self._lecture_seule:
            self.btn_import_pg.setEnabled(False)
            self.btn_import_pg.setToolTip(tr('Lecture seule sur cet espace.'))
            return
        self.btn_import_pg.setEnabled(couche and schema and cible)
        if not couche:
            raison = tr('Ouvrez une couche vectorielle dans QGIS')
        elif not schema:
            raison = tr('Indiquez le schéma cible')
        elif not cible:
            raison = tr('Indiquez le nom de la table à créer')
        else:
            raison = tr('Copier la couche QGIS dans la base de l\'instance')
        self.btn_import_pg.setToolTip(raison)

    def _do_diagnostic_db(self):
        """Analyse la base de l'instance. Aucune écriture."""
        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user'], pg['password']]):
            self._log(
                tr("Informations de connexion à la base indisponibles : "
                'impossible de diagnostiquer.'),
                'warn',
            )
            return

        self._problemes = []
        self.btn_diag_pg.setEnabled(False)
        self.btn_optim_pg.setEnabled(False)
        self.lst_sante.clear()
        self.grp_sante.setVisible(True)
        self.lbl_sante.setText(tr('Analyse en cours…'))

        self._diag_worker = DiagnosticDbWorker(pg, session=self.session)
        self._diag_worker.status.connect(lambda m: self._log(m))
        self._diag_worker.finished.connect(self._on_diagnostic_pret)
        self._diag_worker.error.connect(self._on_diagnostic_erreur)
        self._start_loading(tr('Diagnostic de la base…'))
        self._diag_worker.finished.connect(lambda _: self._stop_loading())
        self._diag_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._diag_worker)
        self._diag_worker.start()

    def _on_diagnostic_erreur(self, message):
        self.btn_diag_pg.setEnabled(True)
        self.lbl_sante.setText(tr('Diagnostic impossible.'))
        self._log(message, 'error')

    def _on_diagnostic_pret(self, problemes):
        self.btn_diag_pg.setEnabled(True)
        self._problemes = problemes
        self.lst_sante.clear()

        if not problemes:
            self.lbl_sante.setText(
                tr('Aucun problème détecté : index spatiaux en place, '
                'statistiques à jour, géométries raisonnables.')
            )
            self.btn_optim_pg.setEnabled(False)
            self._log(tr('Diagnostic : rien à corriger.'), 'ok')
            return

        for probleme in problemes:
            couleur, _ = self._COULEURS_GRAVITE[probleme.gravite]
            if probleme.automatique:
                correction = tr('Automatique')
            elif probleme.confirmable:
                correction = tr('Sur confirmation')
            else:
                correction = tr('À la main')
            item = QTreeWidgetItem(
                [probleme.cible, probleme.titre, correction, probleme.detail]
            )
            item.setForeground(1, QColor(couleur))
            item.setForeground(2, QColor(
                _C_SUCCESS if probleme.automatique else
                _C_WARN if probleme.confirmable else _C_MUTED))
            # Le SQL en infobulle sur toute la ligne, pas seulement une colonne
            infobulle = (probleme.sql or '').strip()
            if probleme.consequence:
                infobulle = probleme.consequence + '\n\n' + infobulle
            if probleme.annulation:
                infobulle += tr('\n\nPour défaire :\n{0}', probleme.annulation)
            for colonne in range(4):
                item.setToolTip(colonne, infobulle)
            item.setData(0, Qt.ItemDataRole.UserRole, probleme)
            self.lst_sante.addTopLevelItem(item)

        auto = [p for p in problemes if p.automatique]
        confirmer = [p for p in problemes if p.confirmable]
        manuel = len(problemes) - len(auto) - len(confirmer)
        resume = tr('{0} point(s) à améliorer.', len(problemes))
        if auto:
            resume += tr(' {0} corrigeable(s) tout de suite.', len(auto))
        if confirmer:
            resume += (tr(' {0} applicable(s) en les sélectionnant, après confirmation.', len(confirmer)))
        if manuel:
            resume += (tr(' {0} demande(nt) une décision de votre part (survolez la ligne pour voir le SQL).', manuel))
        self.lbl_sante.setText(resume)
        self._sync_optim_buttons()
        self._log(resume, 'warn')

    def _problemes_selectionnes(self):
        """Les problèmes des lignes sélectionnées, corrigeables seulement."""
        retenus = []
        for item in self.lst_sante.selectedItems():
            probleme = item.data(0, Qt.ItemDataRole.UserRole)
            if probleme is not None and probleme.applicable:
                retenus.append(probleme)
        return retenus

    def _sync_optim_buttons(self):
        """Ajuste les deux boutons au contenu du tableau et à la sélection."""
        # « Tout optimiser » ne prend que les corrections sans consequence.
        # Celles qui en ont une doivent etre choisies une par une.
        if self._lecture_seule:
            for bouton in (self.btn_optim_pg, self.btn_optim_sel):
                bouton.setEnabled(False)
                bouton.setToolTip(
                    tr('Lecture seule : le diagnostic reste disponible, pas '
                    'la correction.')
                )
            return

        tous = [p for p in getattr(self, '_problemes', []) if p.automatique]
        choisis = self._problemes_selectionnes()

        self.btn_optim_pg.setEnabled(bool(tous))
        self.btn_optim_pg.setText(
            tr('Tout optimiser ({0})', len(tous)) if tous else tr('Tout optimiser')
        )
        self.btn_optim_pg.setToolTip(
            tr('Appliquer les {0} corrections automatiques', len(tous)) if tous
            else tr('Aucune correction automatique disponible')
        )

        self.btn_export_sante.setEnabled(
            bool(getattr(self, '_problemes', []))
        )
        self.btn_optim_sel.setEnabled(bool(choisis))
        self.btn_optim_sel.setText(
            tr('Optimiser la sélection ({0})', len(choisis)) if choisis
            else tr('Optimiser la sélection')
        )
        selection = len(self.lst_sante.selectedItems())
        if choisis:
            raison = tr('Appliquer les {0} corrections sélectionnées', len(choisis))
        elif selection:
            raison = (tr('Les lignes sélectionnées demandent une décision de votre '
                      'part : survolez-les pour voir le SQL à exécuter.'))
        else:
            raison = tr('Sélectionnez une ou plusieurs lignes dans le tableau')
        self.btn_optim_sel.setToolTip(raison)

    def _do_exporter_sante(self):
        """Enregistre le diagnostic en CSV ou en SQL, au choix."""
        problemes = getattr(self, '_problemes', [])
        if not problemes:
            return

        from .optimisation import exporter_csv, exporter_sql
        pg = self.session.get_postgis_uri()
        instance = self.session.instance_name or 'instance'
        base = pg.get('dbname', '')

        horodatage = datetime.now().strftime('%Y%m%d-%H%M')
        defaut = os.path.join(
            self._repertoire_travail(),
            f'diagnostic-{instance}-{horodatage}.csv',
        )
        CSV = tr('Rapport CSV (*.csv)')
        SQL = tr('Script SQL (*.sql)')
        chemin, filtre = QFileDialog.getSaveFileName(
            self, tr('Exporter le diagnostic'), defaut, f'{CSV};;{SQL}',
        )
        if not chemin:
            return

        # Le choix du filtre prime sur l'extension tapee : c'est lui que
        # l'utilisateur a vu au moment de decider.
        if filtre == SQL:
            contenu = exporter_sql(problemes, instance, base)
            if not chemin.lower().endswith('.sql'):
                chemin = os.path.splitext(chemin)[0] + '.sql'
        else:
            contenu = exporter_csv(problemes, instance, base)
            if not chemin.lower().endswith('.csv'):
                chemin = os.path.splitext(chemin)[0] + '.csv'

        try:
            with open(chemin, 'w', encoding='utf-8', newline='') as f:
                f.write(contenu)
        except OSError as e:
            self._log(tr('Export impossible : {0}', e), 'error')
            return

        self._definir_repertoire_travail(os.path.dirname(chemin))
        self._log(tr('{0} point(s) exporté(s) → {1}', len(problemes), chemin), 'ok')

    def _do_optimiser_db(self, selection_seule=False):
        """Applique les corrections sûres, après confirmation."""
        auto = (self._problemes_selectionnes() if selection_seule
                else [p for p in getattr(self, '_problemes', []) if p.automatique])
        if not auto:
            return

        details = '\n'.join(f'  • {p.cible} — {p.titre.lower()}' for p in auto[:12])
        if len(auto) > 12:
            details += tr('\n  … et {0} autre(s)', len(auto) - 12)

        avec_consequence = [p for p in auto if p.confirmable]
        texte = (tr('{0} correction(s) vont être appliquées :\n\n{1}\n\n', len(auto), details))
        if avec_consequence:
            # Une modification de schema ne doit pas passer dans le meme
            # souffle qu'un ANALYZE : elle est nommee a part.
            texte += tr('MODIFICATIONS DE STRUCTURE :\n')
            for p in avec_consequence:
                texte += f'  • {p.cible} : {p.consequence}\n'
            texte += '\n'
        texte += (tr('Les autres opérations créent des index ou rafraîchissent '
                  'des statistiques : elles ne touchent ni au schéma ni aux '
                  'données.\n\nContinuer ?'))
        reponse = QMessageBox.question(
            self, tr('Optimiser la base ?'), texte,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reponse != QMessageBox.StandardButton.Yes:
            self._log(tr('Optimisation annulée.'), 'warn')
            return

        pg = self.session.get_postgis_uri()
        self.btn_optim_pg.setEnabled(False)
        self.btn_optim_sel.setEnabled(False)
        self.btn_diag_pg.setEnabled(False)
        self._optim_worker = OptimiserDbWorker(pg, auto)
        self._optim_worker.status.connect(lambda m: self._log(m))
        self._optim_worker.finished.connect(self._on_optimisation_finie)
        self._optim_worker.error.connect(
            lambda e: (self._log(e, 'error'),
                       self.btn_diag_pg.setEnabled(True),
                       self._sync_optim_buttons())
        )
        self._start_loading(tr('Optimisation de la base…'))
        self._optim_worker.finished.connect(lambda *_: self._stop_loading())
        self._optim_worker.error.connect(lambda _: self._stop_loading())
        self._suivre(self._optim_worker)
        self._optim_worker.start()

    def _on_optimisation_finie(self, reussies, echouees):
        self.btn_diag_pg.setEnabled(True)
        for probleme in reussies:
            self._log(tr('✓ {0} : {1}', probleme.cible, probleme.titre.lower()), 'ok')
        # Tout ce qui vient d'etre cree peut se defaire : le dire ici evite
        # d'avoir a chercher le nom que PostgreSQL aurait choisi seul.
        annulations = [p.annulation for p in reussies if p.annulation]
        if annulations:
            self._log(
                tr('Pour revenir en arrière :\n  {0};', ';\n  '.join(annulations)),
            )
        for probleme, motif in echouees:
            self._log(tr('✗ {0} : {1}', probleme.cible, motif), 'error')

        if echouees:
            self._log(
                tr('{0} correction(s) appliquée(s), {1} en échec.', len(reussies), len(echouees)), 'warn',
            )
        else:
            self._log(tr('{0} correction(s) appliquée(s).', len(reussies)), 'ok')
        # Relancer le diagnostic pour montrer l'etat reel apres coup, plutot
        # que de laisser une liste perimee a l'ecran.
        self._do_diagnostic_db()

    def _refresh_import_layers(self):
        """Rafraîchit le combo avec les couches vectorielles du projet QGIS."""
        self.cmb_import_layer.blockSignals(True)
        self.cmb_import_layer.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                self.cmb_import_layer.addItem(layer.name(), layer.id())
        self.cmb_import_layer.blockSignals(False)
        if self.cmb_import_layer.count() > 0:
            self._on_import_layer_changed(0)

    def _on_import_layer_changed(self, idx):
        """Auto-remplit le nom de table à partir du nom de la couche."""
        if idx < 0:
            return
        name = self.cmb_import_layer.currentText()
        safe = ''.join(c if c.isalnum() or c == '_' else '_' for c in name).lower().strip('_')
        if safe and safe[0].isdigit():
            safe = 'tbl_' + safe
        self.txt_import_table.setText(safe or 'import')

    def _do_import_to_postgis(self):
        """Importe la couche QGIS sélectionnée dans PostGIS."""
        if self._check_quota_block('import PostGIS'):
            return
        if not self.session.is_connected():
            self._log(tr('Connectez-vous d\'abord à une instance.'), 'warn')
            return

        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user']]):
            self._log(tr('PostGIS non disponible pour cette instance.'), 'error')
            return

        layer_id = self.cmb_import_layer.currentData()
        if not layer_id:
            self._log(tr('Sélectionnez une couche à importer.'), 'warn')
            return

        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer):
            self._log(tr('Couche introuvable ou non vectorielle.'), 'error')
            return

        schema = self.txt_import_schema.text().strip() or 'public'
        table  = self.txt_import_table.text().strip()
        if not table:
            self._log(tr('Indiquez un nom de table.'), 'warn')
            return

        self._log(tr('Import de « {0} » → {1}.{2}…', layer.name(), schema, table))
        self.btn_import_pg.setEnabled(False)
        self._start_loading(tr('Import dans PostGIS…'))

        self._import_worker = ImportToPostGISWorker(layer, pg, schema, table)
        self._import_worker.finished.connect(lambda: (
            self._stop_loading(),
            self.btn_import_pg.setEnabled(True),
            self._log(tr('Table « {0}.{1} » importée avec succès.', schema, table), 'ok'),
            self._load_postgis_tables(),
        ))
        self._import_worker.error.connect(lambda e: (
            self._stop_loading(),
            self.btn_import_pg.setEnabled(True),
            self._log(tr('Erreur import : {0}', e), 'error'),
        ))
        self._suivre(self._import_worker)
        self._import_worker.start()

    # ══════════════════════════════════════════════════════════════════
    # Fichiers
    # ══════════════════════════════════════════════════════════════════

    def _load_files(self):
        # Inutile d'interroger le serveur pour se faire refuser : le
        # message serait moins clair que celui du bandeau.
        if self._lecture_seule:
            return

        if not self.session.is_connected():
            return
        path = self._current_path
        self._start_loading(tr('Chargement de {0}…', path))
        self._list_worker = ListFilesWorker(self.session, path)
        self._list_worker.finished.connect(self._on_files_loaded)
        self._list_worker.error.connect(self._on_files_error)
        self._suivre(self._list_worker)
        self._list_worker.start()

    def _on_files_loaded(self, files):
        self._stop_loading()
        self.tree.clear()
        self._populate_tree(files)
        self.lbl_path.setText(self._current_path)
        self.btn_back.setEnabled(self._current_path != '/')
        self._suggerer_destination()
        self._log(tr('{0} élément(s) chargé(s).', len(files)))

    def _suggerer_destination(self, force=False):
        """Propose de publier dans le dossier ou l'on se trouve.

        La destination etait suggeree une seule fois, a l'ouverture du
        projet, et valait la racine. Descendre dans un dossier n'y changeait
        rien : le projet repartait a la racine sans que le champ, pourtant
        sous les yeux, n'ait bouge.

        Un fichier choisi d'un clic reste prioritaire — c'est une decision,
        pas une suggestion — jusqu'a ce qu'on change de dossier.
        """
        nom = os.path.basename(QgsProject.instance().fileName() or '')
        if not nom:
            return
        if self._dest_choisie and not force:
            return
        dossier = (self._current_path or '/').rstrip('/')
        self.txt_publish_dest.setText('{}/{}'.format(dossier, nom))

    def _on_files_error(self, msg):
        self._stop_loading()
        self._log(tr('Impossible de lister les fichiers : {0}', msg), 'error')

    def _nav_back(self):
        if self._path_history:
            self._current_path = self._path_history.pop()
            self._entrer_dans_dossier()
            self._load_files()

    # Couleurs de badge par extension
    # Extension → (svg_name, color)
    _FILE_TYPE_ICONS = {
        '.qgs':    ('map',       _C_PRIMARY),
        '.qgz':    ('map',       _C_PRIMARY),
        '.gpkg':   ('database',  '#8e44ad'),
        '.shp':    ('layers',    _C_SECONDARY),
        '.geojson': ('layers',    _C_SECONDARY),
        '.json':   ('layers',    _C_SECONDARY),
        '.tif':    ('image',     '#d35400'),
        '.tiff':   ('image',     '#d35400'),
        '.png':    ('image',     '#d35400'),
        '.jpg':    ('image',     '#d35400'),
        '.jpeg':   ('image',     '#d35400'),
        '.pdf':    ('file-text', '#B91C1C'),
        '.zip':    ('archive',   '#7f8c8d'),
        '.csv':    ('file-text', '#27ae60'),
        '.xlsx':   ('file-text', '#27ae60'),
        '.xml':    ('file-text', '#2980b9'),
        '.qml':    ('save',      '#16a085'),
        '.sld':    ('save',      '#16a085'),
    }

    def _populate_tree(self, files):
        ICO_SIZE = 20

        def _file_icon(name, is_dir):
            """SVG icon prioritaire, fallback badge lettre si rendu échoue."""
            if is_dir:
                ico = _icon('folder', '#e67e22', ICO_SIZE)
                return ico if not ico.isNull() else _letter_icon(name, '#e67e22', ICO_SIZE)
            ext          = os.path.splitext(name)[1].lower()
            svg_name, color = self._FILE_TYPE_ICONS.get(ext, ('file-text', _C_MUTED))
            ico = _icon(svg_name, color, ICO_SIZE)
            return ico if not ico.isNull() else _letter_icon(
                ext.lstrip('.').upper() or name, color, ICO_SIZE
            )

        for f in sorted(files, key=lambda x: (not x['is_dir'], x['name'].lower())):
            name     = f['name']
            size     = f['size']
            mtime    = f['modified']
            api_path = f['api_path']
            is_dir   = f['is_dir']

            ico = _file_icon(name, is_dir)

            if is_dir:
                # Un dossier n'a pas de taille propre : la calculer voudrait
                # dire parcourir tout son contenu, dossier par dossier, a
                # chaque affichage. Le serveur, lui, a compte ses elements
                # en le listant : c'est ce compte qu'on montre.
                enfants = f.get('enfants')
                if enfants is None:
                    size_str = '·'
                elif enfants == 0:
                    size_str = 'vide'
                else:
                    size_str = tr('{} élément{}').format(
                        enfants, 's' if enfants > 1 else '')
            else:
                size_str = (
                    f'{size / 1_048_576:.1f} MB' if size > 1_048_576
                    else f'{size // 1024} KB' if size > 1024
                    else f'{size} B'
                )
            try:
                # L'heure compte autant que la date : on republie plusieurs
                # fois le meme projet dans une journee, et la seule date ne
                # disait pas laquelle des versions etait en ligne.
                date_str = datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M')
            except Exception as e:
                journal.ignorer(e, 'date de modification illisible')
                date_str = ''

            item = QTreeWidgetItem([name, size_str, date_str])
            item.setIcon(0, ico)
            item.setData(0, Qt.ItemDataRole.UserRole,     api_path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, f.get('id'))
            item.setData(0, Qt.ItemDataRole.UserRole + 2, is_dir)
            self.tree.addTopLevelItem(item)

        self._sync_open_button()

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════
    # Loader
    # ══════════════════════════════════════════════════════════════════

    def _start_loading(self, msg=tr('En cours…')):
        self._busy_count += 1
        self._loader_msg = msg
        self._spinner_idx = 0
        self._loader_lbl.setVisible(True)
        self._loader_bar.setVisible(True)
        self._spinner_timer.start()
        self._tick_spinner()

    def _stop_loading(self):
        self._busy_count = max(0, self._busy_count - 1)
        if self._busy_count == 0:
            self._spinner_timer.stop()
            self._loader_lbl.setVisible(False)
            self._loader_bar.setVisible(False)

    def _tick_spinner(self):
        c = self._spinner_chars[self._spinner_idx % len(self._spinner_chars)]
        self._loader_lbl.setText(tr('{0}  {1}', c, getattr(self, "_loader_msg", "En cours…")))
        self._spinner_idx += 1

    def _refresh_auth_state(self):
        auth      = self.session.is_authenticated()
        connected = self.session.is_connected()
        for i in range(1, 4):
            self.tabs.setTabEnabled(i, connected)

        if connected:
            name = self.session.instance_name
            self.lbl_status.setText(tr('● {0}', name))
            # --color-success-bg / text sur fond sombre → teinte claire
            self.lbl_status.setStyleSheet(
                f'font-size: 13px; font-weight: 600; color: {_C_SUCCESS_BG};'
                f'padding: 4px 12px; background: rgba(16,185,129,.2);'
                f'border-radius: 9999px; border: 1px solid rgba(16,185,129,.4);'
            )
        elif auth:
            self.lbl_status.setText(tr('● Authentifié'))
            self.lbl_status.setStyleSheet(
                f'font-size: 13px; font-weight: 500; color: {_C_WARN_BG};'
                f'padding: 4px 12px; background: rgba(245,158,11,.2);'
                f'border-radius: 9999px; border: 1px solid rgba(245,158,11,.4);'
            )
        else:
            self.lbl_status.setText(tr('○ Non connecté'))
            self.lbl_status.setStyleSheet(
                'font-size: 13px; font-weight: 400; color: rgba(255,255,255,.5);'
                'padding: 4px 10px; background: rgba(255,255,255,.06);'
                'border-radius: 9999px; border: 1px solid rgba(255,255,255,.12);'
            )

    def _log(self, msg, level='info', deployer=True):
        """Ecrit dans le journal.

        `deployer` a False pour une erreur deja montree ailleurs : le
        rapport de validation, par exemple, affiche ses signalements dans
        son propre panneau. Deplier le journal par-dessus n'apprend rien
        et pousse le panneau hors de l'ecran.
        """
        # Une erreur ne doit pas passer inapercue parce que le journal
        # etait replie : on le deploie pour la montrer.
        if deployer and level == 'error' and getattr(self, '_journal_replie', False):
            # Deploye pour cette fois, sans retenir le choix : passer par
            # _basculer_journal() enregistrait l'etat, et la premiere
            # erreur venue faisait du journal ouvert le nouveau defaut.
            self._appliquer_etat_journal(False)
        ts = datetime.now().strftime('%H:%M:%S')
        # Couleurs issues du design system
        colors = {
            'ok':    _C_SUCCESS,   # #10B981
            'error': _C_ERROR,     # #EF4444
            'warn':  _C_WARN,      # #F59E0B
            'info':  '#94A3B8',    # --text-tertiary dark
        }
        color  = colors.get(level, '#94A3B8')
        prefix = {'ok': '✓', 'error': '✗', 'warn': '!', 'info': '·'}.get(level, '·')
        self.log.append(
            f'<span style="color:#475569;">[{ts}]</span> '
            f'<span style="color:{color};">{prefix} {msg}</span>'
        )


# ══════════════════════════════════════════════════════════════════════════════
# UI factory helpers
# ══════════════════════════════════════════════════════════════════════════════

def _btn(label: str, icon_name: str, icon_color: str, style: str) -> QPushButton:
    """Create a styled button with an SVG icon."""
    b = QPushButton(f'  {label}')
    b.setIcon(_icon(icon_name, icon_color, 15))
    b.setIconSize(QSize(15, 15))
    b.setStyleSheet(style)
    return b


class _Lignes:
    """Formulaire en pile de lignes (libellé à largeur fixe + champ)."""

    def __init__(self, parent):
        self.pile = QVBoxLayout(parent)
        self.pile.setSpacing(12)

    def addRow(self, libelle, champ):
        ligne = QWidget()
        h = QHBoxLayout(ligne)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        if not isinstance(libelle, QLabel):
            libelle = QLabel(libelle)
        libelle.setFixedWidth(110)
        libelle.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(libelle)
        h.addWidget(champ, 1)
        self.pile.addWidget(ligne)
        return ligne


def _form_label(text: str) -> QLabel:
    """Styled form row label."""
    lbl = QLabel(tr('{0} :', text))
    lbl.setStyleSheet(f'color: {_C_TEXT}; font-size: 12px; font-weight: 500;')
    lbl.setMinimumWidth(100)
    return lbl


def _version_du_plugin():
    """Lit la version dans metadata.txt, seule source qui fasse foi.

    Le bandeau affichait « v2 » en dur : il ne bougeait plus depuis
    longtemps et ne disait donc rien de ce qui tournait. Si le fichier
    est illisible, mieux vaut ne rien affirmer qu'annoncer une version
    fausse.
    """
    import configparser

    chemin = os.path.join(os.path.dirname(__file__), 'metadata.txt')
    lecteur = configparser.ConfigParser()
    try:
        lecteur.read(chemin, encoding='utf-8')
        return lecteur.get('general', 'version').strip()
    except Exception as e:
        journal.ignorer(e, 'lecture de la version du plugin')
        return '?'


def _liste_deroulante(combo):
    """Prepare une liste deroulante propre.

    La liste native de Windows ignore les regles ::item de la feuille de
    style : il faut une vue Qt pour qu'elles prennent. Cette vue vit dans
    un conteneur — une fenetre surgissante — qui dessine son propre cadre ;
    c'est a lui qu'on donne l'apparence, sinon deux bordures se
    superposent.
    """
    vue = QListView()
    combo.setView(vue)
    conteneur = vue.parentWidget()
    if conteneur is not None:
        conteneur.setStyleSheet(
            'background: {}; border: 1px solid {}; border-radius: 8px;'.format(
                _C_CARD, _C_BORDER)
        )
    return combo


def _input_with_icon(placeholder: str,
                     password: bool = False) -> QLineEdit:
    """QLineEdit — the icon is purely decorative (added as left padding via CSS)."""
    w = QLineEdit()
    # Le remplissage de la feuille de style ne protege pas d'un ecrasement :
    # sans plancher explicite, un champ serre rend son texte illisible.
    w.setMinimumHeight(36)
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.EchoMode.Password)
    return w
