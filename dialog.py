"""
dialog.py
─────────
Interface professionnelle LIZPACK Publisher v2.
Icônes SVG (Feather Icons), palette navy/bleu, design carte.
Flow : email + password → JWT → dropdown instances → connexion instance
"""
import os
import tempfile
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QHeaderView, QAbstractItemView,
    QSizePolicy, QFrame, QMenu, QInputDialog, QMessageBox, QAction,
)
from qgis.PyQt.QtCore import Qt, QByteArray, QSize, QTimer, QUrl, QSettings
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtSvg import QSvgRenderer

from qgis.core import QgsProject, QgsDataSourceUri, QgsVectorLayer

from .sftp_client import LizpackSession
from .workers import (
    LoginWorker, ConnectInstanceWorker, UploadFolderWorker,
    DownloadProjectWorker, SaveSymbologyWorker, ListFilesWorker,
    DeleteWorker, CreateFolderWorker, RenameWorker, UploadFilesWorker,
    ImportToPostGISWorker,
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
    pm.fill(Qt.transparent)
    p  = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


def _letter_icon(letter: str, bg: str, size: int = 20) -> QIcon:
    """Badge carré avec la première lettre en blanc — fiable sur toutes plateformes."""
    from qgis.PyQt.QtGui import QColor, QFont, QBrush, QPen
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p  = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(bg)))
    p.setPen(QPen(Qt.NoPen))
    radius = size * 0.22
    p.drawRoundedRect(0, 0, size, size, radius, radius)
    p.setPen(QColor('white'))
    f = QFont()
    f.setPixelSize(max(8, int(size * 0.56)))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, (letter or '?')[0].upper())
    p.end()
    return QIcon(pm)



# ══════════════════════════════════════════════════════════════════════════════
# Design tokens — alignés sur le design system LIZPACK
# ══════════════════════════════════════════════════════════════════════════════

# Couleurs primaires (identiques au design system web)
_C_PRIMARY       = '#083D44'   # --color-primary
_C_PRIMARY_LIGHT = '#0a4a53'   # --color-primary-light
_C_PRIMARY_DARK  = '#062d32'   # --color-primary-dark
_C_SECONDARY     = '#3D9B4E'   # --color-secondary
_C_SECONDARY_LT  = '#4db15f'   # --color-secondary-light
_C_SECONDARY_DK  = '#2d7a3c'   # --color-secondary-dark

# ← _C_BLUE supprimé : utiliser _C_INFO (#3B82F6) à la place

# Fond / surfaces
_C_BG     = '#F5F7FA'   # --bg-primary
_C_CARD   = '#FFFFFF'   # --bg-secondary
_C_BG_TER = '#F9FAFB'   # --bg-tertiary
_C_HOVER  = '#F3F4F6'   # --bg-hover

# Texte
_C_TEXT   = '#1a1a1a'   # --text-primary
_C_MUTED  = '#6B7280'   # --text-secondary
_C_FAINT  = '#9CA3AF'   # --text-tertiary

# Bordures
_C_BORDER = '#E5E7EB'   # --border-primary

# États
_C_SUCCESS    = '#10B981'
_C_SUCCESS_BG = '#D1FAE5'
_C_SUCCESS_TX = '#065F46'
_C_ERROR      = '#EF4444'
_C_ERROR_BG   = '#FEE2E2'
_C_ERROR_TX   = '#991B1B'
_C_WARN       = '#F59E0B'
_C_WARN_BG    = '#FEF3C7'
_C_WARN_TX    = '#92400E'
_C_INFO       = '#3B82F6'
_C_INFO_BG    = '#DBEAFE'
_C_INFO_TX    = '#1E40AF'

_BTN_PRIMARY = f"""
QPushButton {{
    background: {_C_PRIMARY}; color: white;
    border-radius: 8px; padding: 9px 20px;
    font-size: 14px; font-weight: 600; border: none;
}}
QPushButton:hover    {{ background: {_C_PRIMARY_LIGHT}; }}
QPushButton:pressed  {{ background: {_C_PRIMARY_DARK}; }}
QPushButton:disabled {{ background: {_C_FAINT}; color: rgba(255,255,255,.6); }}
"""

_BTN_SUCCESS = f"""
QPushButton {{
    background: {_C_SECONDARY}; color: white;
    border-radius: 8px; padding: 9px 20px;
    font-size: 14px; font-weight: 600; border: none;
}}
QPushButton:hover    {{ background: {_C_SECONDARY_LT}; }}
QPushButton:pressed  {{ background: {_C_SECONDARY_DK}; }}
QPushButton:disabled {{ background: {_C_FAINT}; color: rgba(255,255,255,.6); }}
"""

_BTN_GHOST = f"""
QPushButton {{
    background: transparent; color: {_C_MUTED};
    border-radius: 8px; padding: 8px 16px;
    font-size: 14px; font-weight: 500;
    border: 1.5px solid {_C_BORDER};
}}
QPushButton:hover    {{ background: {_C_HOVER}; color: {_C_TEXT}; border-color: {_C_MUTED}; }}
QPushButton:pressed  {{ background: {_C_BG_TER}; }}
QPushButton:disabled {{ color: {_C_FAINT}; border-color: {_C_BORDER}; }}
"""

_BTN_ICON = f"""
QPushButton {{
    background: {_C_BG_TER}; color: {_C_MUTED};
    border-radius: 8px; padding: 6px;
    border: 1px solid {_C_BORDER};
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
}}
QPushButton:hover   {{ background: {_C_HOVER}; color: {_C_TEXT}; }}
QPushButton:pressed {{ background: {_C_BORDER}; }}
"""

_QSS = f"""
QDialog {{
    background: {_C_BG};
    font-family: "Segoe UI", "Urbanist", Arial, sans-serif;
}}

/* ── Tabs ─────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {_C_BORDER};
    border-radius: 0 8px 8px 8px;
    background: {_C_BG};
    top: -1px;
}}
QTabBar::tab {{
    background: {_C_BG_TER};
    color: {_C_MUTED};
    padding: 9px 18px;
    border: 1px solid {_C_BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 3px;
    font-size: 14px;
    font-weight: 500;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background: {_C_BG};
    color: {_C_PRIMARY};
    font-weight: 700;
    border-color: {_C_BORDER};
}}
QTabBar::tab:hover:!selected {{
    background: {_C_HOVER};
    color: {_C_TEXT};
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
QComboBox:disabled {{ background: {_C_BG_TER}; color: {_C_FAINT}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid {_C_BORDER};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: {_C_BG_TER};
}}
QComboBox QAbstractItemView {{
    border: 1px solid {_C_BORDER};
    border-radius: 8px;
    background: {_C_CARD};
    selection-background-color: {_C_SUCCESS_BG};
    selection-color: {_C_SUCCESS_TX};
    padding: 4px;
    outline: none;
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
_FILE_ICONS = {
    '.qgz': ('map',       _C_PRIMARY),
    '.qgs': ('map',       _C_PRIMARY),
    '.gpkg':('database',  '#8e44ad'),
    '.shp': ('layers',    _C_SECONDARY),
    '.geojson': ('layers', _C_SECONDARY),
    '.tif': ('image',     '#d35400'),
    '.tiff':('image',     '#d35400'),
    '.png': ('image',     '#d35400'),
    '.jpg': ('image',     '#d35400'),
    '.pdf': ('file-text', _C_ERROR),
    '.zip': ('archive',   _C_MUTED),
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

        self.setWindowTitle('LIZPACK Publisher')
        self.setMinimumSize(640, 720)
        self.setWindowFlags(Qt.Window)
        self.setStyleSheet(_QSS)
        self._build_ui()
        self._refresh_auth_state()
        # Détecter les changements de projet dans QGIS
        QgsProject.instance().readProject.connect(self._on_qgis_project_changed)

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
        self.tabs.setIconSize(QSize(15, 15))

        t_conn = self._tab_connexion()
        t_proj = self._tab_projets()
        t_upld = self._tab_upload()
        t_pg   = self._tab_postgis()
        t_docs = self._tab_docs()

        self.tabs.addTab(t_conn, _icon('lock',         _C_PRIMARY, 15), '  Connexion')
        self.tabs.addTab(t_proj, _icon('layers',       _C_PRIMARY, 15), '  Projets')
        self.tabs.addTab(t_upld, _icon('upload-cloud', _C_PRIMARY, 15), '  Upload')
        self.tabs.addTab(t_pg,   _icon('database',     _C_PRIMARY, 15), '  PostGIS')
        self.tabs.addTab(t_docs, _icon('book-open',    _C_PRIMARY, 15), '  Aide')
        body.addWidget(self.tabs)

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
        lbl_sub = QLabel('v2')
        lbl_sub.setStyleSheet('font-size: 12px; color: rgba(255,255,255,.45);')
        titles.addWidget(lbl_title)
        titles.addWidget(lbl_sub)
        h.addLayout(titles)
        h.addStretch()

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
        return self.log

    # ── Onglet Aide / Documentation ──────────────────────────────────
    def _tab_docs(self):
        # NOTE prod : remplacer accept.lizpack.com par lizpack.com
        _SUPPORT_URL = 'https://accept.lizpack.com/client/aide-support'

        from qgis.PyQt.QtWidgets import QScrollArea

        tab         = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
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
            sep.setFrameShape(QFrame.HLine)
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
            badge.setAlignment(Qt.AlignCenter)
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

            row.addWidget(badge, 0, Qt.AlignTop)
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
            row.addWidget(ico, 0, Qt.AlignTop)
            row.addWidget(lbl, 1)
            return f

        # ══════════════════════════════════════════════════════════════
        # SECTION 1 — Premiers pas
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title('Premiers pas', 'zap', _C_SECONDARY))
        v.addWidget(_step(1, 'Se connecter',
            'Dans l\'onglet Connexion, entrez votre email et mot de passe LIZPACK, '
            'puis cliquez sur Se connecter.'))
        v.addWidget(_step(2, 'Choisir une instance',
            'Sélectionnez votre instance dans la liste déroulante (statut RUNNING = active), '
            'puis cliquez sur Connecter à l\'instance.'))
        v.addWidget(_step(3, 'Naviguer dans les fichiers',
            'L\'onglet Projets affiche vos fichiers. Double-cliquez sur un dossier pour y entrer. '
            'Utilisez ← Retour pour remonter.'))
        v.addWidget(_tip(
            'Vos identifiants sont ceux de votre espace client LIZPACK (accept.lizpack.com).',
            'info'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 2 — Ouvrir un projet
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title('Ouvrir un projet depuis le serveur', 'download', _C_PRIMARY))
        v.addWidget(_step(1, 'Localiser le fichier .qgs ou .qgz',
            'Naviguez dans l\'arborescence jusqu\'au fichier projet.'))
        v.addWidget(_step(2, 'Double-cliquer ou cliquer Ouvrir',
            'Le projet est téléchargé dans un dossier temporaire local avec toutes ses données '
            '(shapefiles, rasters, GeoJSON…). Le chemin reproduit la structure du serveur.'))
        v.addWidget(_step(3, 'QGIS charge le projet',
            'Les couches sont disponibles immédiatement. Si des fichiers manquent sur le serveur, '
            'un avertissement s\'affiche dans la console.'))
        v.addWidget(_tip(
            'Les fichiers téléchargés sont placés dans %TEMP%/lizpack/ — ils sont réutilisés '
            'lors du prochain téléchargement du même projet.', 'ok'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 3 — Publier un projet
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title('Publier un projet vers Lizmap', 'upload-cloud', _C_SECONDARY))
        v.addWidget(_step(1, 'Ouvrir ou créer un projet dans QGIS',
            'Tout projet ouvert dans QGIS peut être publié — qu\'il vienne du serveur ou d\'un '
            'fichier local.'))
        v.addWidget(_step(2, 'Définir la destination',
            'Cliquez sur un fichier dans l\'arbre pour pré-remplir le chemin de destination, '
            'ou saisissez-le manuellement (ex: /qgis/mon-projet.qgs).'))
        v.addWidget(_step(3, 'Cliquer sur Publier vers Lizmap',
            'Le projet est sauvegardé localement puis uploadé sur le serveur. '
            'Lizmap recharge automatiquement la configuration.'))
        v.addWidget(_tip(
            'Après publication, vérifiez que votre fichier lizmap_plugin_print.qgs (si existant) '
            'est aussi à jour sur le serveur.', 'warn'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 4 — Gestion des fichiers
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title('Gestion des fichiers', 'folder-plus', '#e67e22'))
        v.addWidget(_step(1, 'Créer un dossier',
            'Cliquez sur l\'icône 📁+ ou faites un clic droit → Nouveau dossier ici.'))
        v.addWidget(_step(2, 'Uploader des fichiers',
            'Cliquez sur l\'icône ↑ pour sélectionner un ou plusieurs fichiers locaux '
            'à envoyer dans le dossier courant.'))
        v.addWidget(_step(3, 'Renommer / Supprimer',
            'Sélectionnez un élément et cliquez sur les icônes ✏️ ou 🗑, '
            'ou utilisez le clic droit. La suppression demande confirmation.'))
        v.addWidget(_tip('La sélection multiple (Ctrl+clic) permet de supprimer plusieurs éléments d\'un coup.', 'info'))

        # ══════════════════════════════════════════════════════════════
        # SECTION 5 — PostGIS
        # ══════════════════════════════════════════════════════════════
        v.addWidget(_section_title('Connexion PostGIS', 'database', '#8e44ad'))
        v.addWidget(_step(1, 'Vérifier la disponibilité',
            'L\'onglet PostGIS est disponible uniquement si votre instance dispose d\'une base '
            'PostgreSQL/PostGIS configurée.'))
        v.addWidget(_step(2, 'Charger les tables',
            'Cliquez sur Charger les tables pour lister les couches géométriques disponibles.'))
        v.addWidget(_step(3, 'Ajouter une couche dans QGIS',
            'Double-cliquez sur une table pour l\'ajouter directement en tant que couche vectorielle.'))
        v.addWidget(_tip('Si PostGIS n\'est pas disponible, un bandeau jaune s\'affiche dans l\'onglet.', 'warn'))

        # ══════════════════════════════════════════════════════════════
        # Bouton support
        # ══════════════════════════════════════════════════════════════
        v.addSpacing(4)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f'color: {_C_BORDER};')
        v.addWidget(sep2)

        support_row = QHBoxLayout()
        lbl_support = QLabel('Vous ne trouvez pas la réponse ?')
        lbl_support.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; background: transparent;')
        btn_support = _btn('Contacter le support', 'message-circle', _C_TEXT, _BTN_GHOST)
        btn_support.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(_SUPPORT_URL))
        )
        support_row.addWidget(lbl_support)
        support_row.addStretch()
        support_row.addWidget(btn_support)
        v.addLayout(support_row)

        footer = QLabel('LIZPACK Publisher · Plugin QGIS')
        footer.setStyleSheet(f'font-size: 12px; color: {_C_FAINT}; padding: 2px 0;')
        footer.setAlignment(Qt.AlignCenter)
        v.addWidget(footer)

        scroll_area.setWidget(inner)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)
        return tab

    # ── Onglet Connexion ─────────────────────────────────────────────
    def _tab_connexion(self):
        tab = QWidget()
        v   = QVBoxLayout(tab)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        # ── Étape 1
        grp1 = QGroupBox('Étape 1 — Identifiants')
        f1   = QFormLayout(grp1)
        f1.setSpacing(12)
        f1.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.txt_email = _input_with_icon('votre@email.com')
        self.txt_pwd   = _input_with_icon('••••••••', password=True)
        self.txt_pwd.returnPressed.connect(self._do_login)

        f1.addRow(_form_label('Email'),           self.txt_email)
        f1.addRow(_form_label('Mot de passe'),    self.txt_pwd)
        v.addWidget(grp1)

        row1 = QHBoxLayout()
        self.btn_login = _btn('Se connecter', 'lock', 'white', _BTN_PRIMARY)
        self.btn_logout = _btn('Déconnexion', 'log-out', _C_MUTED, _BTN_GHOST)
        self.btn_logout.setEnabled(False)
        self.btn_login.clicked.connect(self._do_login)
        self.btn_logout.clicked.connect(self._do_logout)
        row1.addWidget(self.btn_login)
        row1.addWidget(self.btn_logout)
        row1.addStretch()
        v.addLayout(row1)

        # ── Étape 2
        self.grp_instance = QGroupBox('Étape 2 — Sélectionner une instance')
        self.grp_instance.setEnabled(False)
        f2 = QFormLayout(self.grp_instance)
        f2.setSpacing(12)
        f2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cmb_instance = QComboBox()
        self.cmb_instance.setMinimumWidth(300)
        f2.addRow(_form_label('Instance'), self.cmb_instance)
        v.addWidget(self.grp_instance)

        row2 = QHBoxLayout()
        self.btn_connect = _btn("Connecter à l'instance", 'link', 'white', _BTN_SUCCESS)
        self.btn_connect.setEnabled(False)
        self.btn_connect.clicked.connect(self._do_connect_instance)
        row2.addWidget(self.btn_connect)
        row2.addStretch()
        v.addLayout(row2)

        self.lbl_instance_info = QLabel('')
        self.lbl_instance_info.setStyleSheet(
            f'color: {_C_SUCCESS_TX}; font-size: 13px; font-weight: 600; padding: 4px 2px;'
        )
        v.addWidget(self.lbl_instance_info)
        v.addStretch()
        return tab

    # ── Onglet Projets ───────────────────────────────────────────────
    def _tab_projets(self):
        tab = QWidget()
        v   = QVBoxLayout(tab)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        # ── Barre de navigation ──────────────────────────────────────
        nav = QHBoxLayout()
        nav.setSpacing(6)
        self.btn_back = QPushButton('← Retour')
        self.btn_back.setToolTip('Remonter au dossier parent')
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
        self.lbl_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.lbl_path)
        v.addLayout(nav)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Fichier', 'Taille', 'Modifié'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().resizeSection(1, 80)
        self.tree.header().resizeSection(2, 90)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_file_dblclick)
        self.tree.itemClicked.connect(self._on_file_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        v.addWidget(self.tree)

        # Raccourcis clavier sur l'arbre
        from qgis.PyQt.QtWidgets import QShortcut
        from qgis.PyQt.QtGui import QKeySequence
        QShortcut(QKeySequence.Copy,  self.tree, self._do_copy)
        QShortcut(QKeySequence('Ctrl+X'), self.tree, self._do_cut)
        QShortcut(QKeySequence.Paste, self.tree, self._do_paste)
        QShortcut(QKeySequence.Delete, self.tree, self._do_delete_selected)

        # ── Barre d'actions fichiers ─────────────────────────────────
        acts = QHBoxLayout()
        acts.setSpacing(4)

        self.btn_open = _btn('Ouvrir', 'download', 'white', _BTN_PRIMARY)
        self.btn_open.setToolTip('Ouvrir le projet .qgs/.qgz sélectionné dans QGIS')
        self.btn_open.clicked.connect(self._do_open_project)

        btn_mkdir = QPushButton()
        btn_mkdir.setIcon(_icon('folder-plus', _C_MUTED, 15))
        btn_mkdir.setIconSize(QSize(15, 15))
        btn_mkdir.setToolTip('Nouveau dossier')
        btn_mkdir.setStyleSheet(_BTN_ICON)
        btn_mkdir.clicked.connect(self._do_create_folder)

        btn_upload_here = QPushButton()
        btn_upload_here.setIcon(_icon('upload', _C_MUTED, 15))
        btn_upload_here.setIconSize(QSize(15, 15))
        btn_upload_here.setToolTip('Uploader des fichiers ici')
        btn_upload_here.setStyleSheet(_BTN_ICON)
        btn_upload_here.clicked.connect(self._do_upload_here)

        btn_upload_folder_here = QPushButton()
        btn_upload_folder_here.setIcon(_icon('folder-upload', _C_PRIMARY, 15))
        btn_upload_folder_here.setIconSize(QSize(15, 15))
        btn_upload_folder_here.setToolTip('Uploader un dossier ici')
        btn_upload_folder_here.setStyleSheet(_BTN_ICON)
        btn_upload_folder_here.clicked.connect(self._do_upload_folder_here)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(_icon('trash-2', '#e74c3c', 15))
        self.btn_delete.setIconSize(QSize(15, 15))
        self.btn_delete.setToolTip('Supprimer la sélection')
        self.btn_delete.setStyleSheet(_BTN_ICON)
        self.btn_delete.clicked.connect(self._do_delete_selected)

        btn_rename = QPushButton()
        btn_rename.setIcon(_icon('edit-2', _C_MUTED, 15))
        btn_rename.setIconSize(QSize(15, 15))
        btn_rename.setToolTip('Renommer')
        btn_rename.setStyleSheet(_BTN_ICON)
        btn_rename.clicked.connect(self._do_rename_selected)

        btn_reload = QPushButton()
        btn_reload.setIcon(_icon('refresh', _C_MUTED, 15))
        btn_reload.setIconSize(QSize(15, 15))
        btn_reload.setToolTip('Rafraîchir')
        btn_reload.setStyleSheet(_BTN_ICON)
        btn_reload.clicked.connect(self._load_files)

        acts.addWidget(self.btn_open)
        acts.addWidget(btn_mkdir)
        acts.addWidget(btn_upload_here)
        acts.addWidget(btn_upload_folder_here)
        acts.addWidget(self.btn_delete)
        acts.addWidget(btn_rename)
        acts.addStretch()
        acts.addWidget(btn_reload)
        v.addLayout(acts)

        # ── Section Publication ──────────────────────────────────────
        pub_grp = QGroupBox('Publier vers Lizmap')
        pub_grp.setStyleSheet(
            f'QGroupBox {{ font-weight: 600; font-size: 13px; color: {_C_TEXT};'
            f'  border: 1px solid {_C_BORDER}; border-radius: 8px; margin-top: 8px;'
            f'  padding-top: 10px; background: {_C_CARD}; }}'
            f'QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}'
        )
        pub_v = QVBoxLayout(pub_grp)
        pub_v.setSpacing(6)
        pub_v.setContentsMargins(10, 8, 10, 10)

        # Projet actif détecté dans QGIS
        row_local = QHBoxLayout()
        lbl_l = QLabel('Projet actif :')
        lbl_l.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; min-width: 90px;')
        self.lbl_local_project = QLabel('Aucun projet ouvert dans QGIS')
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_TEXT}; font-style: italic;'
        )
        self.lbl_local_project.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_local.addWidget(lbl_l)
        row_local.addWidget(self.lbl_local_project, 1)
        pub_v.addLayout(row_local)

        # Chemin de destination sur le serveur
        row_dest = QHBoxLayout()
        lbl_d = QLabel('Destination :')
        lbl_d.setStyleSheet(f'font-size: 13px; color: {_C_MUTED}; min-width: 90px;')
        self.txt_publish_dest = QLineEdit()
        self.txt_publish_dest.setReadOnly(True)
        self.txt_publish_dest.setPlaceholderText(
            'Sélectionnez un fichier ou un dossier dans la liste ci-dessus'
        )
        row_dest.addWidget(lbl_d)
        row_dest.addWidget(self.txt_publish_dest, 1)
        pub_v.addLayout(row_dest)

        self.btn_publish = _btn('Publier vers Lizmap', 'upload-cloud', 'white', _BTN_SUCCESS)
        self.btn_publish.setToolTip(
            'Sauvegarde le projet QGIS actif et le publie sur le serveur.\n'
            'Fonctionne avec n\'importe quel projet ouvert dans QGIS.\n'
            'Lizmap recharge automatiquement.'
        )
        self.btn_publish.clicked.connect(self._do_publish_project)
        pub_v.addWidget(self.btn_publish)

        v.addWidget(pub_grp)
        return tab

    # ── Onglet Upload ────────────────────────────────────────────────
    def _tab_upload(self):
        tab = QWidget()
        v   = QVBoxLayout(tab)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        grp = QGroupBox('Uploader un dossier vers l\'instance')
        f   = QFormLayout(grp)
        f.setSpacing(12)
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        local_row = QHBoxLayout()
        local_row.setSpacing(6)
        self.txt_local = QLineEdit()
        self.txt_local.setPlaceholderText('Sélectionner un dossier local…')
        self.txt_local.setReadOnly(True)
        btn_browse = QPushButton()
        btn_browse.setIcon(_icon('folder', _C_MUTED, 15))
        btn_browse.setIconSize(QSize(15, 15))
        btn_browse.setStyleSheet(_BTN_ICON)
        btn_browse.clicked.connect(self._browse_folder)
        local_row.addWidget(self.txt_local)
        local_row.addWidget(btn_browse)
        f.addRow(_form_label('Dossier local'), local_row)

        self.txt_remote = QLineEdit('/')
        self.txt_remote.setReadOnly(True)
        self.txt_remote.setPlaceholderText('Sélectionnez un dossier local')
        f.addRow(_form_label('Destination'), self.txt_remote)
        v.addWidget(grp)

        self.btn_upload = _btn('Uploader le dossier', 'upload-cloud', 'white', _BTN_PRIMARY)
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
        from qgis.PyQt.QtWidgets import QScrollArea, QSplitter

        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(10, 14, 10, 10)
        v.setSpacing(8)

        info_frame = QFrame()
        info_frame.setStyleSheet(
            f'QFrame {{ background: {_C_INFO_BG}; border: 1px solid #93C5FD; '
            f'border-radius: 8px; padding: 2px; }}'
        )
        info_h = QHBoxLayout(info_frame)
        info_h.setContentsMargins(12, 10, 12, 10)
        info_ico = QLabel()
        info_ico.setPixmap(_icon('alert-circle', _C_INFO, 16).pixmap(16, 16))
        info_ico.setStyleSheet('background: transparent;')
        info_lbl = QLabel(
            'Double-cliquez sur une table pour l\'ajouter comme couche dans QGIS.\n'
            'Connexion directe : QGIS → PostgreSQL de votre instance.'
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(
            f'color: {_C_INFO_TX}; font-size: 13px; background: transparent;'
        )
        info_h.addWidget(info_ico, 0, Qt.AlignTop)
        info_h.addSpacing(8)
        info_h.addWidget(info_lbl)
        v.addWidget(info_frame)

        # Bandeau affiché quand PostGIS n'est pas disponible
        self.pg_unavailable = QFrame()
        self.pg_unavailable.setStyleSheet(
            f'QFrame {{ background: {_C_WARN_BG}; border: 1px solid #FCD34D;'
            f'  border-radius: 8px; }}'
        )
        pu_h = QHBoxLayout(self.pg_unavailable)
        pu_h.setContentsMargins(12, 10, 12, 10)
        pu_ico = QLabel()
        pu_ico.setPixmap(_icon('alert-triangle', _C_WARN, 16).pixmap(16, 16))
        pu_ico.setStyleSheet('background: transparent;')
        pu_lbl = QLabel(
            'PostGIS non disponible pour cette instance.\n'
            'L\'instance doit être déployée avec une base de données PostgreSQL/PostGIS\n'
            'pour utiliser cette fonctionnalité.'
        )
        pu_lbl.setWordWrap(True)
        pu_lbl.setStyleSheet(
            f'color: {_C_WARN_TX}; font-size: 13px; background: transparent;'
        )
        pu_h.addWidget(pu_ico, 0, Qt.AlignTop)
        pu_h.addSpacing(8)
        pu_h.addWidget(pu_lbl)
        self.pg_unavailable.setVisible(False)
        v.addWidget(self.pg_unavailable)

        self.lst_pg = QTreeWidget()
        self.lst_pg.setHeaderLabels(['Table', 'Schéma', 'Géométrie', 'SRID'])
        self.lst_pg.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lst_pg.setAlternatingRowColors(True)
        self.lst_pg.setMinimumHeight(150)
        self.lst_pg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lst_pg.itemDoubleClicked.connect(
            lambda item, _: self._add_postgis_layer(item)
        )
        v.addWidget(self.lst_pg, 1)

        btns = QHBoxLayout()
        self.btn_load_pg = _btn('Charger les tables', 'refresh', _C_PRIMARY, _BTN_GHOST)
        self.btn_load_pg.clicked.connect(self._load_postgis_tables)
        self.btn_add_pg = _btn('Ajouter à QGIS', 'plus-circle', 'white', _BTN_SUCCESS)
        self.btn_add_pg.clicked.connect(
            lambda: self._add_postgis_layer(self.lst_pg.currentItem())
        )
        btns.addWidget(self.btn_load_pg)
        btns.addStretch()
        btns.addWidget(self.btn_add_pg)
        v.addLayout(btns)

        # ── Section Import dans PostGIS ──────────────────────────
        import_grp = QGroupBox('Importer une couche dans PostGIS')
        ig = QVBoxLayout(import_grp)
        ig.setSpacing(8)
        ig.setContentsMargins(12, 14, 12, 12)

        # Ligne 1 : Couche QGIS
        lbl_layer = QLabel('Couche QGIS')
        lbl_layer.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        ig.addWidget(lbl_layer)
        layer_row = QHBoxLayout()
        layer_row.setSpacing(6)
        self.cmb_import_layer = QComboBox()
        self.cmb_import_layer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cmb_import_layer.setMinimumWidth(0)
        self.cmb_import_layer.currentIndexChanged.connect(self._on_import_layer_changed)
        btn_refresh_layers = QPushButton()
        btn_refresh_layers.setIcon(_icon('refresh', _C_MUTED, 15))
        btn_refresh_layers.setIconSize(QSize(15, 15))
        btn_refresh_layers.setToolTip('Rafraîchir la liste des couches')
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
        lbl_schema = QLabel('Schéma')
        lbl_schema.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        self.txt_import_schema = QLineEdit()
        self.txt_import_schema.setPlaceholderText('schéma cible')
        schema_col.addWidget(lbl_schema)
        schema_col.addWidget(self.txt_import_schema)
        schema_table_row.addLayout(schema_col, 1)

        table_col = QVBoxLayout()
        table_col.setSpacing(3)
        lbl_table = QLabel('Table')
        lbl_table.setStyleSheet(f'font-size: 12px; font-weight: 500; color: {_C_MUTED};')
        self.txt_import_table = QLineEdit()
        self.txt_import_table.setPlaceholderText('nom_table')
        table_col.addWidget(lbl_table)
        table_col.addWidget(self.txt_import_table)
        schema_table_row.addLayout(table_col, 2)

        ig.addLayout(schema_table_row)

        # Bouton import (dans le GroupBox, pleine largeur)
        self.btn_import_pg = _btn('Importer dans PostGIS', 'upload', 'white', _BTN_PRIMARY)
        self.btn_import_pg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.btn_import_pg.setToolTip(
            'Envoyer la couche sélectionnée dans la base PostGIS de l\'instance'
        )
        self.btn_import_pg.clicked.connect(self._do_import_to_postgis)
        ig.addWidget(self.btn_import_pg)

        v.addWidget(import_grp)

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════
    # Actions — Connexion
    # ══════════════════════════════════════════════════════════════════

    def _do_login(self):
        email    = self.txt_email.text().strip()
        password = self.txt_pwd.text()
        if not email or not password:
            self._log('Email et mot de passe requis.', 'warn')
            return
        self.btn_login.setEnabled(False)
        self.btn_login.setText('Connexion…')
        self._log('Authentification en cours…')
        self._login_worker = LoginWorker(self.session, email, password)
        self._login_worker.finished.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._start_loading('Authentification…')
        self._login_worker.finished.connect(lambda _: self._stop_loading())
        self._login_worker.error.connect(lambda _: self._stop_loading())
        self._login_worker.start()

    def _on_login_success(self, instances):
        self.btn_login.setText('Se connecter')
        self._log(f'{len(instances)} instance(s) disponible(s).', 'ok')
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
                'RUNNING': 'En cours',
                'STOPPED': 'Arrêtée',
                'SUSPENDED_BILLING': 'Suspendue (abonnement)',
                'SUSPENDED_QUOTA': 'Suspendue (quota)',
                'SUSPENDED': 'Suspendue',
                'DEPLOYING': 'Déploiement…',
                'ERROR': 'Erreur',
            }.get(status, status)
            self.cmb_instance.addItem(
                f"{dot}{inst['name']}  ({label_status})", userData=inst
            )
        self.grp_instance.setEnabled(True)
        self.btn_connect.setEnabled(len(instances) > 0)
        self.btn_logout.setEnabled(True)
        self.btn_login.setEnabled(False)
        self._refresh_auth_state()

    def _on_login_error(self, msg):
        self.btn_login.setEnabled(True)
        self.btn_login.setText('Se connecter')
        self._log(msg.strip(), 'error')

    def _do_connect_instance(self):
        inst = self.cmb_instance.currentData()
        if not inst:
            self._log('Sélectionnez une instance.', 'warn')
            return

        status = inst.get('status', '').upper()
        if status == 'SUSPENDED_BILLING':
            self._log(
                'Cette instance est suspendue (abonnement expiré).\n'
                'Renouvelez votre abonnement depuis votre espace client '
                '(Facturation) pour réactiver l\'instance.',
                'error',
            )
            return
        if status == 'SUSPENDED_QUOTA':
            self._log(
                'Cette instance est suspendue (quota dépassé).\n'
                'Vous avez dépassé les limites de stockage de votre plan.\n'
                'La base de données PostgreSQL reste accessible pour '
                'vous permettre de libérer de l\'espace.\n'
                'Supprimez des données puis vérifiez votre quota depuis '
                'votre espace client.',
                'error',
            )
            # On autorise la connexion pour que l'onglet PostGIS reste utilisable
            self._quota_suspended = True
        elif status == 'SUSPENDED':
            self._log(
                'Cette instance est suspendue.\n'
                'Vérifiez votre abonnement depuis votre espace client '
                '(Facturation) pour réactiver l\'instance.',
                'error',
            )
            return
        elif status == 'STOPPED':
            self._log(
                'Cette instance est arrêtée.\n'
                'Démarrez-la depuis votre tableau de bord avant de vous connecter.',
                'warn',
            )
            return
        elif status not in ('RUNNING', 'DEPLOYING'):
            self._log(
                f'Instance indisponible (statut : {status}).\n'
                'Vérifiez son état depuis votre tableau de bord.',
                'warn',
            )
            return
        else:
            self._quota_suspended = False

        # Réinitialiser l'état de l'instance précédente si on change
        if self.session.is_connected():
            prev = self.session.instance_name
            self._log(f'Déconnexion de « {prev} »…')
            self._reset_instance_state()

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText('Connexion…')
        self._log(f"Connexion à \"{inst['name']}\"…")
        self._connect_worker = ConnectInstanceWorker(
            self.session, inst['id'], inst['name']
        )
        self._connect_worker.finished.connect(self._on_instance_connected)
        self._connect_worker.error.connect(self._on_instance_connect_error)
        self._start_loading(f"Connexion à \"{inst['name']}\"…")
        self._connect_worker.finished.connect(lambda: self._stop_loading())
        self._connect_worker.error.connect(lambda _: self._stop_loading())
        self._connect_worker.start()

    def _on_instance_connected(self):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("Connecter à l'instance")
        name = self.session.instance_name
        self.lbl_instance_info.setText(f'Instance connectée : {name}')
        self._log(f'Connecté à {name}', 'ok')
        self._current_path = '/'
        self._path_history = []
        self._refresh_auth_state()
        self._register_qgis_pg_connection()
        self._refresh_import_layers()
        self._load_files()

    def _on_instance_connect_error(self, msg):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("Connecter à l'instance")
        self._log(msg.strip(), 'error')

    def _register_qgis_pg_connection(self):
        """Enregistre une connexion PostgreSQL dans QGIS automatiquement
        pour que les couches PostGIS fonctionnent sans configuration manuelle."""
        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user']]):
            return
        conn_name = f'LizPack - {self.session.instance_name}'
        s = QSettings()
        prefix = f'PostgreSQL/connections/{conn_name}'
        s.setValue(f'{prefix}/host', pg['host'])
        s.setValue(f'{prefix}/port', pg['port'])
        s.setValue(f'{prefix}/database', pg['dbname'])
        s.setValue(f'{prefix}/username', pg['user'])
        s.setValue(f'{prefix}/password', pg['password'])
        s.setValue(f'{prefix}/saveUsername', True)
        s.setValue(f'{prefix}/savePassword', True)
        s.setValue(f'{prefix}/sslmode', 2)  # prefer
        self._registered_pg_conn = conn_name
        self._log(f'Connexion PostgreSQL « {conn_name} » enregistrée dans QGIS.', 'ok')
        try:
            self.iface.browserModel().reload()
        except Exception:
            pass

    def _unregister_qgis_pg_connection(self):
        """Supprime la connexion PostgreSQL enregistrée par le plugin."""
        conn_name = self._registered_pg_conn
        if not conn_name:
            return
        s = QSettings()
        s.remove(f'PostgreSQL/connections/{conn_name}')
        self._registered_pg_conn = None
        try:
            self.iface.browserModel().reload()
        except Exception:
            pass

    def _reset_instance_state(self):
        """Nettoie tout l'état lié à l'instance courante (fichiers, PostGIS, quota, chemins)."""
        self._unregister_qgis_pg_connection()
        self.tree.clear()
        self.lst_pg.clear()
        self._open_project_api_path = None
        self._current_path = '/'
        self._path_history = []
        self._clipboard_ids = None
        self._clipboard_mode = 'copy'
        self._quota_suspended = False
        self.lbl_instance_info.setText('')
        self.lbl_local_project.setText('Aucun projet ouvert dans QGIS')
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_MUTED}; font-style: italic;'
        )
        self.txt_publish_dest.clear()
        self.txt_import_schema.clear()
        self.txt_import_table.clear()

    def _do_logout(self):
        self._reset_instance_state()
        self.session.logout()
        self.cmb_instance.clear()
        self.grp_instance.setEnabled(False)
        self.btn_connect.setEnabled(False)
        self.btn_login.setEnabled(True)
        self.btn_logout.setEnabled(False)
        self._refresh_auth_state()
        self._log('Déconnecté.')

    # ══════════════════════════════════════════════════════════════════
    # Actions — Projets
    # ══════════════════════════════════════════════════════════════════

    def _do_open_project(self):
        item = self.tree.currentItem()
        if not item:
            self._log('Sélectionnez un fichier dans la liste.', 'warn')
            return
        api_path = item.data(0, Qt.UserRole)
        file_id  = item.data(0, Qt.UserRole + 1)
        if not api_path or not api_path.lower().endswith(('.qgz', '.qgs')):
            self._log('Sélectionnez un fichier .qgz ou .qgs.', 'warn')
            return
        fname      = os.path.basename(api_path)
        # Reproduire l'arborescence serveur dans %TEMP%/lizpack/
        # Ex: /qgis/data/projet.qgs → <temp>/lizpack/qgis/data/projet.qgs
        rel        = api_path.lstrip('/')
        local_path = os.path.join(
            tempfile.gettempdir(), 'lizpack',
            rel.replace('/', os.sep),
        )
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._log(f'Téléchargement de {fname} + données associées…')
        self.btn_open.setEnabled(False)
        self._dl_worker = DownloadProjectWorker(self.session, file_id, local_path, api_path)
        self._dl_worker.finished.connect(self._on_project_downloaded)
        self._dl_worker.status.connect(lambda msg: self._log(msg))
        self._dl_worker.error.connect(
            lambda e: (self._log(e, 'error'), self.btn_open.setEnabled(True))
        )
        self._start_loading(f'Téléchargement de {fname}…')
        self._dl_worker.finished.connect(lambda _: self._stop_loading())
        self._dl_worker.error.connect(lambda _: self._stop_loading())
        self._dl_worker.start()

    def _on_project_downloaded(self, local_path):
        self.btn_open.setEnabled(True)
        self._log(f'Téléchargé → {local_path}', 'ok')
        item = self.tree.currentItem()
        self._open_project_api_path = item.data(0, Qt.UserRole) if item else None
        ok = QgsProject.instance().read(local_path)
        if ok:
            fname = os.path.basename(local_path)
            self._log(f'Projet ouvert : {fname}', 'ok')
            # Pré-remplir la section Publication
            self.lbl_local_project.setText(fname)
            self.lbl_local_project.setStyleSheet(
                f'font-size: 13px; color: {_C_SUCCESS_TX}; font-weight: 600;'
            )
            if self._open_project_api_path:
                self.txt_publish_dest.setText(self._open_project_api_path)
        else:
            self._log('Impossible d\'ouvrir le projet dans QGIS.', 'error')

    def _on_qgis_project_changed(self):
        """Détecte quand un projet est ouvert/changé dans QGIS (signal readProject)."""
        project    = QgsProject.instance()
        local_path = project.fileName()
        if not local_path:
            return
        fname = os.path.basename(local_path)
        self.lbl_local_project.setText(fname)
        self.lbl_local_project.setStyleSheet(
            f'font-size: 13px; color: {_C_TEXT}; font-style: normal;'
        )
        # Auto-suggestion de destination si champ vide
        if not self.txt_publish_dest.text():
            self.txt_publish_dest.setText(f'/{fname}')

    def _check_quota_block(self, action='cette action'):
        """Retourne True (et log) si l'instance est suspendue pour quota."""
        if getattr(self, '_quota_suspended', False):
            self._log(
                f'Impossible : {action}.\n'
                'Votre instance est suspendue pour dépassement de quota.\n'
                'Supprimez des fichiers ou des données pour libérer de l\'espace.',
                'error',
            )
            return True
        return False

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
            self._log('Connectez-vous d\'abord à une instance.', 'warn')
            return

        project    = QgsProject.instance()
        local_path = project.fileName()
        if not local_path:
            self._log(
                'Aucun projet QGIS ouvert. '
                'Ouvrez un projet (Ctrl+O) ou créez-en un et sauvegardez-le (Ctrl+S).',
                'warn',
            )
            return

        dest_path = self.txt_publish_dest.text().strip()
        if not dest_path:
            self._log(
                'Indiquez le chemin de destination sur le serveur.\n'
                'Ex: /qgis/mon-projet.qgs — ou sélectionnez un fichier dans la liste.',
                'warn',
            )
            return

        # Normaliser : si dest est un dossier, ajouter le nom du fichier
        if not dest_path.lower().endswith(('.qgs', '.qgz')):
            dest_path = dest_path.rstrip('/') + '/' + os.path.basename(local_path)
            self.txt_publish_dest.setText(dest_path)

        # Sauvegarder automatiquement le projet QGIS
        if not project.write():
            self._log('Échec de la sauvegarde locale du projet.', 'error')
            return

        self._log(f'Publication → {dest_path}…')
        self.btn_publish.setEnabled(False)
        self._save_worker = SaveSymbologyWorker(self.session, local_path, dest_path)
        self._save_worker.finished.connect(self._on_published)
        self._save_worker.error.connect(
            lambda e: (self._log(e, 'error'), self.btn_publish.setEnabled(True))
        )
        self._start_loading('Publication vers Lizmap…')
        self._save_worker.finished.connect(lambda: self._stop_loading())
        self._save_worker.error.connect(lambda _: self._stop_loading())
        self._save_worker.start()

    def _on_published(self):
        self.btn_publish.setEnabled(True)
        self._log('Projet publié — Lizmap recharge automatiquement.', 'ok')
        self._load_files()  # rafraîchir l'arbre

    def _on_file_click(self, item, _col):
        """Clic simple : pré-remplir le champ Destination dans la section Publication."""
        api_path = item.data(0, Qt.UserRole)
        is_dir   = item.data(0, Qt.UserRole + 2)
        if api_path and not is_dir:
            self.txt_publish_dest.setText(api_path)

    def _on_file_dblclick(self, item, _col):
        api_path = item.data(0, Qt.UserRole)
        is_dir   = item.data(0, Qt.UserRole + 2)
        if is_dir:
            self._path_history.append(self._current_path)
            self._current_path = api_path
            self.tree.clear()           # feedback immédiat
            self.lbl_path.setText(api_path)
            self._load_files()
        elif api_path and api_path.lower().endswith(('.qgz', '.qgs')):
            self._do_open_project()

    # ══════════════════════════════════════════════════════════════════
    # Actions — Gestion fichiers (nouveau dossier, supprimer, renommer, upload ici)
    # ══════════════════════════════════════════════════════════════════

    def _show_context_menu(self, pos):
        """Menu clic-droit sur l'arbre."""
        items = self.tree.selectedItems()
        menu  = QMenu(self)

        if items:
            is_dir  = items[0].data(0, Qt.UserRole + 2)
            is_proj = (not is_dir and
                       (items[0].data(0, Qt.UserRole) or '').lower().endswith(('.qgs', '.qgz')))

            if is_proj and len(items) == 1:
                act_open = menu.addAction(_icon('download', 'white', 14), 'Ouvrir dans QGIS')
                act_open.triggered.connect(self._do_open_project)
                menu.addSeparator()

            if len(items) == 1:
                act_rename = menu.addAction(_icon('edit-2', _C_MUTED, 14), 'Renommer')
                act_rename.triggered.connect(self._do_rename_selected)

            lbl_copy = f'Copier ({len(items)})' if len(items) > 1 else 'Copier'
            act_copy = menu.addAction(_icon('copy', _C_MUTED, 14), lbl_copy)
            act_copy.triggered.connect(self._do_copy)

            lbl_cut = f'Couper ({len(items)})' if len(items) > 1 else 'Couper'
            act_cut = menu.addAction(_icon('scissors', _C_MUTED, 14), lbl_cut)
            act_cut.triggered.connect(self._do_cut)

            lbl_del = f'Supprimer ({len(items)})' if len(items) > 1 else 'Supprimer'
            act_del = menu.addAction(_icon('trash-2', '#e74c3c', 14), lbl_del)
            act_del.triggered.connect(self._do_delete_selected)
            menu.addSeparator()

        if getattr(self, '_clipboard_ids', None):
            mode = 'Coller' if self._clipboard_mode == 'copy' else 'Déplacer ici'
            count = len(self._clipboard_ids)
            act_paste = menu.addAction(
                _icon('clipboard', _C_SUCCESS_TX, 14),
                f'{mode} ({count} élément(s))',
            )
            act_paste.triggered.connect(self._do_paste)
            menu.addSeparator()

        act_mkdir = menu.addAction(_icon('folder-plus', _C_MUTED, 14), 'Nouveau dossier ici')
        act_mkdir.triggered.connect(self._do_create_folder)
        act_up = menu.addAction(_icon('upload', _C_MUTED, 14), 'Uploader des fichiers ici')
        act_up.triggered.connect(self._do_upload_here)
        act_up_dir = menu.addAction(_icon('folder-upload', _C_PRIMARY, 14), 'Uploader un dossier ici')
        act_up_dir.triggered.connect(self._do_upload_folder_here)

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _selected_ids(self):
        """Retourne la liste des IDs des items sélectionnés."""
        return [
            item.data(0, Qt.UserRole + 1)
            for item in self.tree.selectedItems()
            if item.data(0, Qt.UserRole + 1) is not None
        ]

    # ── Copier / Couper / Coller ──────────────────────────────────────

    def _do_copy(self):
        ids = self._selected_ids()
        if not ids:
            self._log('Sélectionnez au moins un élément à copier.', 'warn')
            return
        self._clipboard_ids = ids
        self._clipboard_mode = 'copy'
        names = [it.text(0) for it in self.tree.selectedItems()]
        self._log(f'{len(ids)} élément(s) copié(s) : {", ".join(names)}')

    def _do_cut(self):
        ids = self._selected_ids()
        if not ids:
            self._log('Sélectionnez au moins un élément à couper.', 'warn')
            return
        self._clipboard_ids = ids
        self._clipboard_mode = 'cut'
        names = [it.text(0) for it in self.tree.selectedItems()]
        self._log(f'{len(ids)} élément(s) coupé(s) : {", ".join(names)}')

    def _do_paste(self):
        ids = getattr(self, '_clipboard_ids', None)
        if not ids:
            self._log('Rien à coller. Copiez ou coupez d\'abord un élément.', 'warn')
            return
        if not self.session.is_connected():
            return
        mode = getattr(self, '_clipboard_mode', 'copy')
        dest = self._current_path
        count = len(ids)

        if mode == 'copy':
            if self._check_quota_block('copie'):
                return
            action_label = 'Copie'
            self._start_loading(f'Copie de {count} élément(s)…')
            try:
                self.session.copy_files(ids, dest)
                self._stop_loading()
                self._log(f'{count} élément(s) collé(s) dans {dest}', 'ok')
            except Exception as e:
                self._stop_loading()
                self._log(f'Erreur copie : {e}', 'error')
        else:
            action_label = 'Déplacement'
            self._start_loading(f'Déplacement de {count} élément(s)…')
            try:
                self.session.move_files(ids, dest)
                self._stop_loading()
                self._log(f'{count} élément(s) déplacé(s) vers {dest}', 'ok')
                self._clipboard_ids = None  # couper = one-shot
            except Exception as e:
                self._stop_loading()
                self._log(f'Erreur déplacement : {e}', 'error')

        self._load_files()

    def _do_create_folder(self):
        if self._check_quota_block('création de dossier'):
            return
        if not self.session.is_connected():
            return
        name, ok = QInputDialog.getText(self, 'Nouveau dossier', 'Nom du dossier :')
        if not ok or not name.strip():
            return
        name = name.strip()
        self._start_loading(f'Création de "{name}"…')
        self._mkdir_worker = CreateFolderWorker(self.session, name, self._current_path)
        self._mkdir_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                     self._log(f'Dossier "{name}" créé.', 'ok')))
        self._mkdir_worker.error.connect(lambda e: (self._stop_loading(),
                                                    self._log(f'Erreur : {e}', 'error')))
        self._mkdir_worker.start()

    def _do_delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            self._log('Aucun élément sélectionné.', 'warn')
            return
        names = [item.text(0) for item in self.tree.selectedItems()]
        preview = ', '.join(names[:3]) + (f' … +{len(names)-3}' if len(names) > 3 else '')
        rep = QMessageBox.question(
            self, 'Confirmer la suppression',
            f'Supprimer {len(ids)} élément(s) ?\n{preview}',
            QMessageBox.Yes | QMessageBox.No,
        )
        if rep != QMessageBox.Yes:
            return
        self._start_loading(f'Suppression de {len(ids)} élément(s)…')
        self._del_worker = DeleteWorker(self.session, ids)
        self._del_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                   self._log(f'{len(ids)} élément(s) supprimé(s).', 'ok')))
        self._del_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(f'Erreur suppression : {e}', 'error')))
        self._del_worker.start()

    def _do_rename_selected(self):
        items = self.tree.selectedItems()
        if len(items) != 1:
            self._log('Sélectionnez un seul élément pour le renommer.', 'warn')
            return
        item    = items[0]
        file_id = item.data(0, Qt.UserRole + 1)
        old     = item.text(0)
        new_name, ok = QInputDialog.getText(self, 'Renommer', 'Nouveau nom :', text=old)
        if not ok or not new_name.strip() or new_name.strip() == old:
            return
        new_name = new_name.strip()
        self._start_loading(f'Renommage vers "{new_name}"…')
        self._ren_worker = RenameWorker(self.session, file_id, new_name)
        self._ren_worker.finished.connect(lambda: (self._stop_loading(), self._load_files(),
                                                   self._log(f'"{old}" renommé en "{new_name}".', 'ok')))
        self._ren_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(f'Erreur renommage : {e}', 'error')))
        self._ren_worker.start()

    def _do_upload_here(self):
        """Upload un ou plusieurs fichiers dans le dossier courant."""
        if self._check_quota_block('upload de fichiers'):
            return
        if not self.session.is_connected():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, f'Uploader vers {self._current_path}', '', 'Tous les fichiers (*.*)'
        )
        if not paths:
            return
        self._start_loading(f'Upload de {len(paths)} fichier(s)…')
        self._upf_worker = UploadFilesWorker(self.session, paths, self._current_path)
        self._upf_worker.progress.connect(
            lambda cur, tot, fname: self._log(f'  [{cur}/{tot}] {fname}…')
        )
        self._upf_worker.finished.connect(lambda n: (self._stop_loading(), self._load_files(),
                                                     self._log(f'{n} fichier(s) uploadé(s).', 'ok')))
        self._upf_worker.error.connect(lambda e: (self._stop_loading(),
                                                  self._log(f'Erreur upload : {e}', 'error')))
        self._upf_worker.start()

    def _do_upload_folder_here(self):
        """Upload un dossier entier dans le dossier courant via batch."""
        if self._check_quota_block('upload de dossier'):
            return
        if not self.session.is_connected():
            return
        folder = QFileDialog.getExistingDirectory(
            self, f'Uploader un dossier vers {self._current_path}',
        )
        if not folder:
            return
        # Collecter tous les fichiers
        entries = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                if fname.startswith('.'):
                    continue
                local = os.path.join(root, fname)
                rel   = os.path.relpath(local, folder).replace('\\', '/')
                entries.append(local)
        if not entries:
            self._log('Le dossier est vide.', 'warn')
            return
        folder_name = os.path.basename(folder)
        self._log(f'Upload du dossier « {folder_name} » ({len(entries)} fichier(s))…')
        self._start_loading(f'Upload de {len(entries)} fichier(s)…')
        self._updir_worker = UploadFolderWorker(self.session, folder, self._current_path)
        self._updir_worker.progress.connect(
            lambda cur, tot, fname: self._log(f'  [{cur}/{tot}] {fname}…')
        )
        self._updir_worker.finished.connect(lambda n: (self._stop_loading(), self._load_files(),
                                                       self._log(f'{n} fichier(s) uploadé(s).', 'ok')))
        self._updir_worker.error.connect(lambda e: (self._stop_loading(),
                                                    self._log(f'Erreur upload : {e}', 'error')))
        self._updir_worker.start()

    # ══════════════════════════════════════════════════════════════════
    # Actions — Upload dossier (onglet Upload)
    # ══════════════════════════════════════════════════════════════════

    def _do_upload_folder(self):
        if self._check_quota_block('upload de dossier'):
            return
        local  = self.txt_local.text()
        remote = self.txt_remote.text().strip() or '/'
        if not local or not os.path.isdir(local):
            self._log('Sélectionnez un dossier local valide.', 'warn')
            return
        if not self.session.is_connected():
            self._log('Non connecté.', 'warn')
            return
        self.btn_upload.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._log(f'Upload : {local}  →  {remote}…')
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
        self._start_loading('Upload en cours…')
        self._up_worker.finished.connect(lambda _: self._stop_loading())
        self._up_worker.error.connect(lambda _: self._stop_loading())
        self._up_worker.start()

    def _on_upload_progress(self, cur, tot, fname):
        self.progress.setMaximum(tot)
        self.progress.setValue(cur)
        self.lbl_progress.setText(f'{fname}  ({cur} / {tot})')

    def _on_upload_done(self, count):
        self.btn_upload.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_progress.setText('')
        self._log(f'{count} fichier(s) uploadé(s).', 'ok')
        self._load_files()

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Sélectionner un dossier')
        if path:
            self.txt_local.setText(path)
            self.txt_remote.setText('/')

    # ══════════════════════════════════════════════════════════════════
    # Actions — PostGIS
    # ══════════════════════════════════════════════════════════════════

    def _load_postgis_tables(self):
        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user'], pg['password']]):
            self.pg_unavailable.setVisible(True)
            self.lst_pg.setVisible(False)
            self.btn_load_pg.setVisible(False)
            return
        self.pg_unavailable.setVisible(False)
        self.lst_pg.setVisible(True)
        self.btn_load_pg.setVisible(True)
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=pg['host'], port=pg['port'],
                dbname=pg['dbname'], user=pg['user'],
                password=pg['password'], connect_timeout=10,
            )
            cur = conn.cursor()
            # Toutes les tables/vues/vues mat. — colonne géom optionnelle
            cur.execute("""
                SELECT
                    c.relname  AS table_name,
                    n.nspname  AS table_schema,
                    MAX(CASE WHEN t.typname IN ('geometry','geography')
                             THEN a.attname END)  AS geom_col,
                    COALESCE(
                        (SELECT srid FROM geometry_columns g
                         WHERE g.f_table_schema = n.nspname
                           AND g.f_table_name   = c.relname
                         LIMIT 1),
                        0
                    )                             AS srid
                FROM pg_class      c
                JOIN pg_namespace  n ON c.relnamespace = n.oid
                LEFT JOIN pg_attribute a ON a.attrelid = c.oid
                                        AND a.attnum > 0
                                        AND NOT a.attisdropped
                LEFT JOIN pg_type  t ON a.atttypid = t.oid
                WHERE c.relkind IN ('r', 'v', 'm')
                  AND n.nspname NOT IN (
                        'pg_catalog','information_schema',
                        'topology','tiger','tiger_data','public','lizmap'
                      )
                GROUP BY c.relname, n.nspname
                ORDER BY n.nspname, c.relname
            """)
            rows = cur.fetchall()
            cur.close(); conn.close()
        except ImportError:
            self._log('psycopg2 non disponible — utilisation du provider QGIS.')
            self._load_pg_via_qgis(pg)
            return
        except Exception as e:
            self._log(f'Connexion PostGIS échouée : {e}', 'error')
            return

        self.lst_pg.clear()
        db_ico = _icon('database', '#8e44ad', 14)
        for table, schema, geom_col, srid in rows:
            item = QTreeWidgetItem([table, schema, geom_col or '—', str(srid)])
            item.setIcon(0, db_ico)
            item.setData(0, Qt.UserRole, {
                **pg, 'table': table, 'schema': schema,
                'geom_col': geom_col or 'geom',
            })
            self.lst_pg.addTopLevelItem(item)
        self._log(f'{self.lst_pg.topLevelItemCount()} table(s) chargée(s).', 'ok')
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
                    t.geometryColumnName() or '—',
                    str(t.crs().postgisSrid()) if t.crs().isValid() else '—',
                ])
                item.setIcon(0, db_ico)
                item.setData(0, Qt.UserRole, {
                    **pg, 'table': t.tableName(),
                    'schema': t.schema() or 'public',
                    'geom_col': t.geometryColumnName() or '',
                })
                self.lst_pg.addTopLevelItem(item)
            self._log(f'{self.lst_pg.topLevelItemCount()} table(s) chargée(s).', 'ok')
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
            self._log('Sélectionnez une table.', 'warn')
            return
        info = item.data(0, Qt.UserRole)
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
            self._log(f'Couche "{info["table"]}" ajoutée.', 'ok')
        else:
            self._log(
                f'Couche "{info["table"]}" invalide — '
                f'vérifiez que {info["host"]}:{info["port"]} est accessible.',
                'error'
            )

    # ══════════════════════════════════════════════════════════════════
    # Actions — Import PostGIS
    # ══════════════════════════════════════════════════════════════════

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
            self._log('Connectez-vous d\'abord à une instance.', 'warn')
            return

        pg = self.session.get_postgis_uri()
        if not all([pg['host'], pg['dbname'], pg['user']]):
            self._log('PostGIS non disponible pour cette instance.', 'error')
            return

        layer_id = self.cmb_import_layer.currentData()
        if not layer_id:
            self._log('Sélectionnez une couche à importer.', 'warn')
            return

        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer):
            self._log('Couche introuvable ou non vectorielle.', 'error')
            return

        schema = self.txt_import_schema.text().strip() or 'public'
        table  = self.txt_import_table.text().strip()
        if not table:
            self._log('Indiquez un nom de table.', 'warn')
            return

        self._log(f'Import de « {layer.name()} » → {schema}.{table}…')
        self.btn_import_pg.setEnabled(False)
        self._start_loading('Import dans PostGIS…')

        self._import_worker = ImportToPostGISWorker(layer, pg, schema, table)
        self._import_worker.finished.connect(lambda: (
            self._stop_loading(),
            self.btn_import_pg.setEnabled(True),
            self._log(f'Table « {schema}.{table} » importée avec succès.', 'ok'),
            self._load_postgis_tables(),
        ))
        self._import_worker.error.connect(lambda e: (
            self._stop_loading(),
            self.btn_import_pg.setEnabled(True),
            self._log(f'Erreur import : {e}', 'error'),
        ))
        self._import_worker.start()

    # ══════════════════════════════════════════════════════════════════
    # Fichiers
    # ══════════════════════════════════════════════════════════════════

    def _load_files(self):
        if not self.session.is_connected():
            return
        path = self._current_path
        self._start_loading(f'Chargement de {path}…')
        self._list_worker = ListFilesWorker(self.session, path)
        self._list_worker.finished.connect(self._on_files_loaded)
        self._list_worker.error.connect(self._on_files_error)
        self._list_worker.start()

    def _on_files_loaded(self, files):
        self._stop_loading()
        self.tree.clear()
        self._populate_tree(files)
        self.lbl_path.setText(self._current_path)
        self.btn_back.setEnabled(self._current_path != '/')
        self._log(f'{len(files)} élément(s) chargé(s).')

    def _on_files_error(self, msg):
        self._stop_loading()
        self._log(f'Impossible de lister les fichiers : {msg}', 'error')

    def _nav_back(self):
        if self._path_history:
            self._current_path = self._path_history.pop()
            self._load_files()

    # Couleurs de badge par extension
    # Extension → (svg_name, color)
    _FILE_TYPE_ICONS = {
        '.qgs':    ('map',       _C_PRIMARY),
        '.qgz':    ('map',       _C_PRIMARY),
        '.gpkg':   ('database',  '#8e44ad'),
        '.shp':    ('layers',    _C_SECONDARY),
        '.geojson':('layers',    _C_SECONDARY),
        '.json':   ('layers',    _C_SECONDARY),
        '.tif':    ('image',     '#d35400'),
        '.tiff':   ('image',     '#d35400'),
        '.png':    ('image',     '#d35400'),
        '.jpg':    ('image',     '#d35400'),
        '.jpeg':   ('image',     '#d35400'),
        '.pdf':    ('file-text', '#c0392b'),
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
                size_str = '—'
            else:
                size_str = (
                    f'{size / 1_048_576:.1f} MB' if size > 1_048_576
                    else f'{size // 1024} KB'     if size > 1024
                    else f'{size} B'
                )
            try:
                date_str = datetime.fromtimestamp(mtime).strftime('%d/%m/%Y')
            except Exception:
                date_str = ''

            item = QTreeWidgetItem([name, size_str, date_str])
            item.setIcon(0, ico)
            item.setData(0, Qt.UserRole,     api_path)
            item.setData(0, Qt.UserRole + 1, f.get('id'))
            item.setData(0, Qt.UserRole + 2, is_dir)
            self.tree.addTopLevelItem(item)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════
    # Loader
    # ══════════════════════════════════════════════════════════════════

    def _start_loading(self, msg='En cours…'):
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
        self._loader_lbl.setText(f'{c}  {getattr(self, "_loader_msg", "En cours…")}')
        self._spinner_idx += 1

    def _refresh_auth_state(self):
        auth      = self.session.is_authenticated()
        connected = self.session.is_connected()
        for i in range(1, 4):
            self.tabs.setTabEnabled(i, connected)

        if connected:
            name = self.session.instance_name
            self.lbl_status.setText(f'● {name}')
            # --color-success-bg / text sur fond sombre → teinte claire
            self.lbl_status.setStyleSheet(
                f'font-size: 13px; font-weight: 600; color: {_C_SUCCESS_BG};'
                f'padding: 4px 12px; background: rgba(16,185,129,.2);'
                f'border-radius: 9999px; border: 1px solid rgba(16,185,129,.4);'
            )
        elif auth:
            self.lbl_status.setText('● Authentifié')
            self.lbl_status.setStyleSheet(
                f'font-size: 13px; font-weight: 500; color: {_C_WARN_BG};'
                f'padding: 4px 12px; background: rgba(245,158,11,.2);'
                f'border-radius: 9999px; border: 1px solid rgba(245,158,11,.4);'
            )
        else:
            self.lbl_status.setText('○ Non connecté')
            self.lbl_status.setStyleSheet(
                'font-size: 13px; font-weight: 400; color: rgba(255,255,255,.5);'
                'padding: 4px 10px; background: rgba(255,255,255,.06);'
                'border-radius: 9999px; border: 1px solid rgba(255,255,255,.12);'
            )

    def _log(self, msg, level='info'):
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


def _form_label(text: str) -> QLabel:
    """Styled form row label."""
    lbl = QLabel(text + ' :')
    lbl.setStyleSheet(f'color: {_C_TEXT}; font-size: 12px; font-weight: 500;')
    lbl.setMinimumWidth(100)
    return lbl


def _input_with_icon(placeholder: str,
                     password: bool = False) -> QLineEdit:
    """QLineEdit — the icon is purely decorative (added as left padding via CSS)."""
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.Password)
    return w
