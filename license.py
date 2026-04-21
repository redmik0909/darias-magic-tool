import hashlib
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QClipboard

# ── Paths ──────────────────────────────────────────────────────────────────────
_APP_DATA    = os.path.join(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))), "DariasMagicTool")
os.makedirs(_APP_DATA, exist_ok=True)
LICENSE_FILE = os.path.join(_APP_DATA, ".license")

_OLD_LICENSE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license")
if not os.path.exists(LICENSE_FILE) and os.path.exists(_OLD_LICENSE):
    import shutil
    shutil.copy(_OLD_LICENSE, LICENSE_FILE)

SECRET_SALT = "darias-magic-tool-2026-xK9#mP"

COLORS = {
    "sidebar":  "#1e3a5f",
    "bg":       "#f8fafc",
    "surface":  "#ffffff",
    "surface2": "#f1f5f9",
    "border":   "#e2e8f0",
    "text":     "#1e293b",
    "muted":    "#64748b",
    "accent":   "#2563eb",
    "green":    "#16a34a",
    "red":      "#dc2626",
}

# ── License logic ──────────────────────────────────────────────────────────────
def get_hardware_id() -> str:
    parts = [platform.node()]
    try:
        result = subprocess.check_output("wmic cpu get ProcessorId", shell=True, stderr=subprocess.DEVNULL).decode().strip().split("\n")
        cpu_id = [l.strip() for l in result if l.strip() and "ProcessorId" not in l]
        if cpu_id: parts.append(cpu_id[0])
    except Exception:
        pass
    try:
        result = subprocess.check_output("wmic baseboard get SerialNumber", shell=True, stderr=subprocess.DEVNULL).decode().strip().split("\n")
        mb = [l.strip() for l in result if l.strip() and "SerialNumber" not in l]
        if mb: parts.append(mb[0])
    except Exception:
        pass
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16].upper()

def generate_license_key(hardware_id: str) -> str:
    h = hashlib.sha256(f"{SECRET_SALT}:{hardware_id}".encode()).hexdigest().upper()
    return f"{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"

def is_licensed() -> bool:
    if not os.path.exists(LICENSE_FILE):
        return False
    try:
        with open(LICENSE_FILE, "r") as f:
            saved_key = f.read().strip()
        return saved_key == generate_license_key(get_hardware_id())
    except Exception:
        return False

def save_license(key: str) -> bool:
    if key.strip().upper() == generate_license_key(get_hardware_id()):
        with open(LICENSE_FILE, "w") as f:
            f.write(key.strip().upper())
        return True
    return False


# ── Activation Window (PyQt6) ──────────────────────────────────────────────────
class ActivationWindowQt(QDialog):
    def __init__(self, data=None):
        super().__init__()
        self.setWindowTitle("Activation — Daria's Magic Tool")
        self.setFixedSize(480, 360)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['sidebar']};")
        hdr.setFixedHeight(80)
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(0, 12, 0, 12)
        hdr_l.setSpacing(2)

        title = QLabel("Daria's Magic Tool")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        hdr_l.addWidget(title)

        sub = QLabel("Activation requise")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #93c5fd; font-size: 12px;")
        hdr_l.addWidget(sub)
        layout.addWidget(hdr)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background-color: {COLORS['bg']};")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(32, 20, 32, 20)
        body_l.setSpacing(10)

        desc = QLabel("Ce logiciel est protégé par licence.\nEntrez votre clé d'activation pour continuer.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        body_l.addWidget(desc)

        # Hardware ID card
        hw_card = QFrame()
        hw_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        hw_l = QVBoxLayout(hw_card)
        hw_l.setContentsMargins(12, 8, 12, 8)
        hw_l.setSpacing(4)

        hw_title = QLabel("ID de cette machine :")
        hw_title.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px; border: none; background: transparent;")
        hw_l.addWidget(hw_title)

        hw_id = get_hardware_id()
        id_row = QHBoxLayout()

        id_lbl = QLabel(hw_id)
        id_lbl.setStyleSheet(f"color: {COLORS['accent']}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        id_row.addWidget(id_lbl)

        self.copy_btn = QPushButton("Copier")
        self.copy_btn.setFixedSize(70, 26)
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                color: {COLORS['muted']};
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {COLORS['surface2']}; }}
        """)
        self.copy_btn.clicked.connect(lambda: self._copy_id(hw_id))
        id_row.addWidget(self.copy_btn)
        hw_l.addLayout(id_row)
        body_l.addWidget(hw_card)

        # Key entry
        key_lbl = QLabel("Clé d'activation :")
        key_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        body_l.addWidget(key_lbl)

        self.key_entry = QLineEdit()
        self.key_entry.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_entry.setFixedHeight(42)
        self.key_entry.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 14px;
                font-weight: bold;
                background: white;
            }}
        """)
        self.key_entry.returnPressed.connect(self._activate)
        body_l.addWidget(self.key_entry)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px;")
        body_l.addWidget(self.status_lbl)

        activate_btn = QPushButton("Activer")
        activate_btn.setFixedSize(200, 40)
        activate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1d4ed8; }}
        """)
        activate_btn.clicked.connect(self._activate)
        body_l.addWidget(activate_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(body)

    def _copy_id(self, hw_id):
        QApplication.clipboard().setText(hw_id)
        self.copy_btn.setText("Copié!")
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['green']};
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 11px;
            }}
        """)
        QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("Copier")
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                color: {COLORS['muted']};
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {COLORS['surface2']}; }}
        """)

    def _activate(self):
        key = self.key_entry.text().strip()
        if not key:
            self.status_lbl.setText("Entrez une clé d'activation.")
            return
        if save_license(key):
            self.accept()
        else:
            self.status_lbl.setText("Clé invalide pour cette machine.")
            self.key_entry.setStyleSheet(self.key_entry.styleSheet() + f"border: 1px solid {COLORS['red']};")

    def closeEvent(self, event):
        self.status_lbl.setText("Vous devez activer le logiciel pour continuer.")
        event.ignore()


# Legacy CTk class — kept for compatibility during migration
class ActivationWindow:
    def __init__(self, parent, on_success):
        dlg = ActivationWindowQt()
        if dlg.exec():
            on_success()