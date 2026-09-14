"""
Thème gris foncé bleuté élégant (Slate / Navy Blue-Grey) pour IPTV Hub.
Palette lumineuse et moderne sans aucun noir pur.
"""

DARK_THEME = """
/* =========================================================================
   STYLE GLOBAL & PALETTE DE COULEURS (GRIS FONCÉ BLEUTÉ MODERNE)
   ========================================================================= */
* {
    font-family: "Segoe UI", "SF Pro Display", "Ubuntu", "Cantarell", "DejaVu Sans", -apple-system, Roboto, Helvetica, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #1b2232;
}

QWidget {
    background-color: transparent;
}

/* =========================================================================
   BARRE DE TITRE PERSONNALISÉE (CUSTOM TITLE BAR & RECHERCHE INTÉGRÉE)
   ========================================================================= */
#customTitleBar {
    background-color: #161c2a;
    border-bottom: 1px solid #28334a;
    min-height: 48px;
    max-height: 48px;
}

#customTitleBar QComboBox {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
    min-width: 190px;
}

#customTitleBar QComboBox:hover {
    border-color: #6366f1;
    background-color: #273349;
}

#customTitleBar QPushButton.top-btn {
    background-color: #222b3d;
    border: 1px solid #33415c;
    border-radius: 6px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0px;
}

#customTitleBar QPushButton.top-btn:hover {
    background-color: #2e3c56;
    border-color: #6366f1;
}

#topSearchBox {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    min-width: 260px;
    max-width: 440px;
}

#topSearchBox:focus {
    border: 1px solid #6366f1;
    background-color: #273349;
}

#customTitleBar QPushButton.win-ctrl-btn {
    background-color: transparent;
    border: none;
    min-width: 46px;
    max-width: 46px;
    min-height: 48px;
    max-height: 48px;
    padding: 0px;
    border-radius: 0px;
}

#customTitleBar QPushButton.win-ctrl-btn:hover {
    background-color: #263148;
}

#customTitleBar QPushButton.win-close-btn {
    background-color: transparent;
    border: none;
    min-width: 46px;
    max-width: 46px;
    min-height: 48px;
    max-height: 48px;
    padding: 0px;
    border-radius: 0px;
}

#customTitleBar QPushButton.win-close-btn:hover {
    background-color: #e81123;
    color: #ffffff;
}

/* =========================================================================
   MENUS CONTEXTUELS & MENUS POPUP (QMenu)
   ========================================================================= */
QMenu {
    background-color: #222b3d;
    border: 1px solid #364563;
    border-radius: 8px;
    padding: 6px 4px;
    color: #f8fafc;
}

QMenu::item {
    background-color: transparent;
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
    margin: 2px 4px;
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 500;
}

QMenu::item:selected {
    background-color: #4f46e5;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #64748b;
}

QMenu::separator {
    height: 1px;
    background-color: #313e59;
    margin: 4px 8px;
}

/* =========================================================================
   BARRE LATÉRALE (SIDEBAR COMPACTE)
   ========================================================================= */
#sidebar {
    background-color: #141824;
    border-right: 1px solid #252f44;
}

#appLogoTitle {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.5px;
}

/* Boutons de navigation compacts de la sidebar (icônes seules) */
QPushButton.sidebar-icon-btn,
QPushButton[class="sidebar-icon-btn"] {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    padding: 0px;
    margin: 2px 0px;
}

QPushButton.sidebar-icon-btn:hover,
QPushButton[class="sidebar-icon-btn"]:hover {
    background-color: #242e42;
    border-color: #344360;
}

QPushButton.sidebar-icon-btn:checked,
QPushButton[class="sidebar-icon-btn"]:checked {
    background-color: #4f46e5;
    border-color: #6366f1;
}

/* =========================================================================
   BARRE DE SOUS-MENU PARAMÈTRES (SETTINGS SUB-NAVIGATION)
   ========================================================================= */
#settingsNavPanel {
    background-color: #19202e;
    border-right: 1px solid #28344c;
    min-width: 230px;
    max-width: 230px;
}

#settingsNavTitle {
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
    padding: 16px 18px 12px 18px;
    border-bottom: 1px solid #28344c;
}

QPushButton.settings-nav-btn {
    background-color: transparent;
    color: #94a3b8;
    text-align: left;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid transparent;
    margin: 2px 10px;
}

QPushButton.settings-nav-btn:hover {
    background-color: #242e42;
    color: #f1f5f9;
}

QPushButton.settings-nav-btn:checked {
    background-color: #4f46e5;
    color: #ffffff;
    font-weight: 600;
}

/* =========================================================================
   ZONE DE CONTENU DES PARAMÈTRES (CENTRÉE)
   ========================================================================= */
#settingsContentArea {
    background-color: #1b2232;
}

.settings-card {
    background-color: #222b3d;
    border: 1px solid #33415c;
    border-radius: 12px;
    padding: 22px;
}

.settings-card-title {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 8px;
}

.settings-card-desc {
    color: #94a3b8;
    font-size: 12px;
    margin-bottom: 14px;
}

/* =========================================================================
   PANNEAU DE LISTE DES CHAÎNES
   ========================================================================= */
#channelPanel {
    background-color: #1a2130;
    border-right: 1px solid #29354d;
}

#searchBox {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #6366f1;
}

#searchBox:focus {
    border: 1px solid #6366f1;
    background-color: #273349;
}

QComboBox {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #4f6186;
}

QComboBox:focus {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #222b3d;
    border: 1px solid #364563;
    border-radius: 8px;
    color: #e2e8f0;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
    padding: 4px;
}

QLineEdit {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #6366f1;
    background-color: #273349;
}

QSpinBox {
    background-color: #222b3d;
    color: #f8fafc;
    border: 1px solid #33415c;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

/* =========================================================================
   LISTES & CARTES
   ========================================================================= */
QListWidget, QListView {
    background-color: transparent;
    border: none;
    padding: 4px;
}

QListWidget::item, QListView::item {
    background-color: transparent;
    border-radius: 8px;
    margin: 2px 4px;
    padding: 6px;
}

QListWidget::item:hover, QListView::item:hover {
    background-color: #253046;
}

QListWidget::item:selected, QListView::item:selected {
    background-color: transparent;
    border: none;
}

/* =========================================================================
   LECTEUR VIDÉO & CONTROLES
   ========================================================================= */
#videoContainer {
    background-color: #141926;
}

#osdBar {
    background-color: rgba(28, 36, 52, 0.95);
    border: 1px solid #3d4f72;
    border-radius: 12px;
    padding: 0px;
}

QPushButton.osd-btn,
QPushButton.osd-btn:checked {
    background-color: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    color: #ffffff;
    font-size: 14px;
}

QPushButton.osd-btn:hover,
QPushButton.osd-btn:checked:hover {
    background-color: #6366f1;
    border-color: #818cf8;
    color: #ffffff;
}


QPushButton.osd-play-btn {
    background-color: #4f46e5;
    border-radius: 22px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    font-size: 18px;
    color: #ffffff;
}

QPushButton.osd-play-btn:hover {
    background-color: #6366f1;
}

/* =========================================================================
   SLIDERS (Volume & Progression)
   ========================================================================= */
QSlider::groove:horizontal {
    height: 6px;
    background: #313e58;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #6366f1;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #6366f1;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #e0e7ff;
    transform: scale(1.1);
}

/* =========================================================================
   SCROLLBARS ÉLÉGANTES
   ========================================================================= */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #374664;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #5b6f98;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* =========================================================================
   BOUTONS GÉNÉRAUX & DIALOGUES
   ========================================================================= */
QPushButton.primary-btn {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.primary-btn:hover {
    background-color: #6366f1;
}

QPushButton.secondary-btn {
    background-color: #242e42;
    color: #cbd5e1;
    border: 1px solid #374664;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton.secondary-btn:hover {
    background-color: #2f3c56;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #2b3850;
    background-color: #1c2333;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #171c2a;
    color: #94a3b8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #1c2333;
    color: #6366f1;
    font-weight: 600;
    border-bottom: 2px solid #6366f1;
}

QProgressBar {
    background-color: #242e42;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 4px;
}

QToolTip {
    background-color: #222b3d;
    color: #ffffff;
    border: 1px solid #415378;
    padding: 5px 10px;
    border-radius: 6px;
}
"""


def apply_theme(app):
    """Applique le thème sombre gris-bleuté à l'instance QApplication."""
    app.setStyleSheet(DARK_THEME)
