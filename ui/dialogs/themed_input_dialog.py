"""
Dialogue de saisie de texte moderne et élégant pour IPTV Hub.
Respecte scrupuleusement la charte graphique Slate Blue-Grey (#1b2232 / #222b3d).
Remplace avantageusement QInputDialog pour une intégration visuelle parfaite.
"""

from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.icons import get_icon
from core.i18n import tr


class ThemedInputDialog(QDialog):
    """
    Boîte de dialogue de saisie textuelle avec le design Slate Blue-Grey de l'application.
    """
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "",
        label: str = "",
        text: str = "",
        placeholder: str = "",
        icon_name: str = "playlist_add"
    ):
        super().__init__(parent)
        self.setWindowTitle(title or tr("Saisie"))
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setObjectName("themedInputDialog")

        self.setStyleSheet("""
            QDialog#themedInputDialog {
                background-color: #1b2232;
                border: 1px solid #33415c;
                border-radius: 12px;
            }
            QLabel {
                color: #e2e8f0;
                background-color: transparent;
            }
            QLineEdit {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                color: #ffffff;
                selection-background-color: #38bdf8;
                selection-color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #263147;
            }
            QPushButton#btnCancel {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 9px 20px;
                color: #cbd5e1;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#btnCancel:hover {
                background-color: #2d384e;
                border-color: #475569;
                color: #ffffff;
            }
            QPushButton#btnCancel:focus {
                border-color: #38bdf8;
            }
            QPushButton#btnOk {
                background-color: #38bdf8;
                border: none;
                border-radius: 8px;
                padding: 9px 24px;
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#btnOk:hover {
                background-color: #0ea5e9;
            }
            QPushButton#btnOk:focus {
                background-color: #0ea5e9;
                border: 2px solid #ffffff;
            }
            QPushButton#btnOk:disabled {
                background-color: #2b3950;
                color: #64748b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)

        # En-tête : Icône + Titre
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(icon_name, color="#38bdf8").pixmap(24, 24))
        header_row.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f1f5f9; font-size: 15px; font-weight: 700;")
        header_row.addWidget(title_lbl, stretch=1)
        layout.addLayout(header_row)

        # Description / Label du champ
        if label:
            prompt_lbl = QLabel(label)
            prompt_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
            prompt_lbl.setWordWrap(True)
            layout.addWidget(prompt_lbl)

        # Champ de texte
        self.input_edit = QLineEdit(text)
        if placeholder:
            self.input_edit.setPlaceholderText(placeholder)
        self.input_edit.selectAll()
        self.input_edit.textChanged.connect(self._on_text_changed)
        self.input_edit.returnPressed.connect(self._on_enter_pressed)
        layout.addWidget(self.input_edit)

        # Boutons d'action : Annuler & Valider
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self.btn_cancel = QPushButton(tr("Annuler"))
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton(tr("Valider"))
        self.btn_ok.setObjectName("btnOk")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_ok)

        layout.addLayout(btn_row)

        self._on_text_changed(self.input_edit.text())
        self.input_edit.setFocus()

    def _on_text_changed(self, text: str):
        self.btn_ok.setEnabled(bool(text and text.strip()))

    def _on_enter_pressed(self):
        if self.btn_ok.isEnabled():
            self.accept()

    def get_value(self) -> str:
        return self.input_edit.text().strip()

    @classmethod
    def get_text(
        cls,
        parent: Optional[QWidget],
        title: str,
        label: str,
        text: str = "",
        placeholder: str = "",
        icon_name: str = "playlist_add"
    ) -> Tuple[str, bool]:
        """
        Méthode statique équivalente à QInputDialog.getText mais avec un style soigné.
        """
        dlg = cls(parent, title=title, label=label, text=text, placeholder=placeholder, icon_name=icon_name)
        ok = (dlg.exec() == QDialog.DialogCode.Accepted)
        return (dlg.get_value(), ok)
