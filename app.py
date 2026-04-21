import sys
import os
import urllib.request
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QDialog,
    QLineEdit, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QScreen

from utils import load_zones
from license import is_licensed, ActivationWindow

CURRENT_VERSION = "2.5.0"
VERSION_URL     = "https://raw.githubusercontent.com/redmik0909/darias-magic-tool/main/version.txt"
DOWNLOAD_URL    = "https://github.com/redmik0909/darias-magic-tool/releases/latest/download/DariasMagicTool-Setup-latest.exe"

# ── Color palette ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":          "#f8fafc",
    "surface":     "#ffffff",
    "surface2":    "#f1f5f9",
    "border":      "#e2e8f0",
    "text":        "#1e293b",
    "text_muted":  "#64748b",
    "text_dim":    "#94a3b8",
    "accent":      "#2563eb",
    "accent_h":    "#1d4ed8",
    "green":       "#16a34a",
    "green_h":     "#15803d",
    "red":         "#dc2626",
    "orange":      "#d97706",
    "purple":      "#7c3aed",
    "sidebar":     "#1e3a5f",
    "sidebar_dark":"#16305a",
    "sidebar_div": "#2a4a7f",
    "p1":          "#16a34a",
    "p2":          "#d97706",
    "p3":          "#dc2626",
}

def styled_btn(text, color=None, text_color="#ffffff", height=36):
    """Create a styled QPushButton."""
    btn = QPushButton(text)
    bg  = color or COLORS["accent"]
    btn.setFixedHeight(height)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: {text_color};
            border: none;
            border-radius: 6px;
            padding: 0 16px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {_darken(bg)};
        }}
        QPushButton:pressed {{
            background-color: {_darken(bg, 0.85)};
        }}
    """)
    return btn

def _darken(hex_color, factor=0.9):
    """Darken a hex color."""
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"
    except Exception:
        return hex_color


# ── Google setup check ─────────────────────────────────────────────────────────
def _check_google_setup():
    try:
        import keyring
        return bool(keyring.get_password("DariasMagicTool", "google_creds_password"))
    except Exception:
        return False


class GoogleSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration Google Calendar")
        self.setFixedSize(460, 300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['sidebar']};")
        hdr.setFixedHeight(56)
        hdr_layout = QHBoxLayout(hdr)
        hdr_lbl = QLabel("🔐  Configuration requise")
        hdr_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        hdr_layout.addWidget(hdr_lbl)
        layout.addWidget(hdr)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background-color: {COLORS['bg']};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(10)

        lbl1 = QLabel("Premier lancement - entrez le mot de passe pour activer Google Calendar.")
        lbl1.setWordWrap(True)
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
        body_layout.addWidget(lbl1)

        lbl2 = QLabel("Contactez votre administrateur si vous ne l'avez pas.")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        body_layout.addWidget(lbl2)

        self.pwd_entry = QLineEdit()
        self.pwd_entry.setPlaceholderText("Mot de passe...")
        self.pwd_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_entry.setFixedHeight(40)
        self.pwd_entry.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                background: white;
            }}
        """)
        self.pwd_entry.returnPressed.connect(self._confirm)
        body_layout.addWidget(self.pwd_entry)

        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px;")
        self.err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_layout.addWidget(self.err_lbl)

        confirm_btn = styled_btn("✅  Confirmer", COLORS["green"], height=40)
        confirm_btn.setFixedWidth(200)
        confirm_btn.clicked.connect(self._confirm)
        body_layout.addWidget(confirm_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(body)
        self.pwd_entry.setFocus()

    def _confirm(self):
        from crypto_utils import decrypt_with_password
        import keyring
        pwd = self.pwd_entry.text().strip()
        if not pwd:
            self.err_lbl.setText("Entrez un mot de passe.")
            return
        data = decrypt_with_password(pwd)
        if not data:
            self.err_lbl.setText("❌  Mot de passe incorrect. Réessayez.")
            self.pwd_entry.clear()
            return
        keyring.set_password("DariasMagicTool", "google_creds_password", pwd)
        self.accept()

    def closeEvent(self, event):
        event.ignore()  # Can't close without activating


# ── Update check thread ────────────────────────────────────────────────────────
class UpdateChecker(QThread):
    update_available = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "DariasMagicTool"})
            with urllib.request.urlopen(req, timeout=5) as r:
                latest = r.read().decode().strip()
            if latest != CURRENT_VERSION:
                self.update_available.emit(latest)
        except Exception:
            pass


# ── Main Window ────────────────────────────────────────────────────────────────
class DariaApp(QMainWindow):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.setWindowTitle("Daria's Magic Tool")

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.showMaximized()

        self.setStyleSheet(f"background-color: {COLORS['bg']};")
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        sw = QApplication.primaryScreen().size().width()
        sidebar_w = max(160, min(220, int(sw * 0.15)))

        sidebar = QFrame()
        sidebar.setFixedWidth(sidebar_w)
        sidebar.setStyleSheet(f"background-color: {COLORS['sidebar']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo = QFrame()
        logo.setStyleSheet(f"background-color: {COLORS['sidebar_dark']};")
        logo_layout = QVBoxLayout(logo)
        logo_layout.setContentsMargins(0, 20, 0, 18)
        logo_layout.setSpacing(4)

        emoji_lbl = QLabel("✨")
        emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_lbl.setStyleSheet("color: white; font-size: 28px;")
        logo_layout.addWidget(emoji_lbl)

        title_lbl = QLabel("Daria's Magic Tool")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        logo_layout.addWidget(title_lbl)

        sub_lbl = QLabel("by RevolvIT")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet("color: #93c5fd; font-size: 11px;")
        logo_layout.addWidget(sub_lbl)

        sidebar_layout.addWidget(logo)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {COLORS['sidebar_div']};")
        sidebar_layout.addWidget(div)

        # Nav label
        nav_lbl = QLabel("  NAVIGATION")
        nav_lbl.setStyleSheet("color: #4a6a9f; font-size: 9px; font-weight: bold;")
        nav_lbl.setContentsMargins(14, 16, 0, 4)
        sidebar_layout.addWidget(nav_lbl)

        # Nav buttons
        self.nav_buttons = {}
        nav_items = [
            ("accueil",   "🏠", "Accueil"),
            ("recherche", "🔍", "Recherche"),
            ("equipe",    "👥", "Équipe"),
        ]

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 0, 10, 0)
        nav_layout.setSpacing(4)

        for key, icon, text in nav_items:
            btn = QPushButton(f"   {icon}   {text}")
            btn.setFixedHeight(max(36, int(QApplication.primaryScreen().size().height() * 0.055)))
            btn.setCheckable(True)
            btn.setStyleSheet(self._nav_btn_style(False))
            btn.clicked.connect(lambda checked, k=key: self._switch_tab(k))
            nav_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addWidget(nav_widget)
        sidebar_layout.addStretch()

        # Bottom divider
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background-color: {COLORS['sidebar_div']};")
        sidebar_layout.addWidget(div2)

        # Bottom info
        bottom = QFrame()
        bottom.setStyleSheet(f"background-color: {COLORS['sidebar_dark']};")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(14, 10, 14, 10)
        bottom_layout.setSpacing(2)

        rev_lbl = QLabel("RevolvIT")
        rev_lbl.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        bottom_layout.addWidget(rev_lbl)

        ver_lbl = QLabel(f"v{CURRENT_VERSION}")
        ver_lbl.setStyleSheet("color: #4a6a9f; font-size: 10px;")
        bottom_layout.addWidget(ver_lbl)

        sidebar_layout.addWidget(bottom)
        main_layout.addWidget(sidebar)

        # ── Content area ──────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {COLORS['bg']};")

        from pages.accueil import AccueilPage
        from pages.recherche import RecherchePage
        from pages.equipe import EquipePage

        self.pages = {
            "accueil":   AccueilPage(self.data),
            "recherche": RecherchePage(self.data),
            "equipe":    EquipePage(self.data),
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack)

        # Start on accueil
        self._switch_tab("accueil")

        # Check Google credentials
        if not _check_google_setup():
            QTimer.singleShot(500, self._show_google_setup)

        # Check for updates
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self._show_update_popup)
        self.updater.start()

    def _nav_btn_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding-left: 8px;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: #bfdbfe;
                border: none;
                border-radius: 10px;
                text-align: left;
                padding-left: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['sidebar_div']};
            }}
        """

    def _switch_tab(self, tab):
        self.stack.setCurrentWidget(self.pages[tab])
        for key, btn in self.nav_buttons.items():
            btn.setStyleSheet(self._nav_btn_style(key == tab))
        page = self.pages[tab]
        if hasattr(page, "refresh"):
            page.refresh()

    def _show_google_setup(self):
        dlg = GoogleSetupDialog(self)
        dlg.exec()

    def _show_update_popup(self, latest_version):
        dlg = QDialog(self)
        dlg.setWindowTitle("Mise à jour disponible")
        dlg.setFixedSize(420, 220)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['sidebar']};")
        hdr.setFixedHeight(50)
        hdr_l = QHBoxLayout(hdr)
        hdr_lbl = QLabel("🔄  Mise à jour disponible")
        hdr_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        hdr_l.addWidget(hdr_lbl)
        layout.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background-color: {COLORS['bg']};")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(20, 16, 20, 16)

        lbl1 = QLabel(f"Une nouvelle version est disponible : v{latest_version}")
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
        body_l.addWidget(lbl1)

        lbl2 = QLabel(f"Vous utilisez actuellement la version v{CURRENT_VERSION}")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        body_l.addWidget(lbl2)

        body_l.addSpacing(10)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        install_btn = styled_btn("⬇️  Installer maintenant", COLORS["green"], height=38)
        install_btn.setFixedWidth(200)
        install_btn.clicked.connect(lambda: self._download_update(dlg))
        btn_row.addWidget(install_btn)

        later_btn = styled_btn("Plus tard", COLORS["surface2"], COLORS["text_muted"], height=38)
        later_btn.setFixedWidth(100)
        later_btn.setStyleSheet(later_btn.styleSheet() + f"border: 1px solid {COLORS['border']};")
        later_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(later_btn)

        btn_row.addStretch()
        body_l.addLayout(btn_row)
        layout.addWidget(body)
        dlg.exec()

    def _download_update(self, parent_dlg):
        import tempfile, subprocess, webbrowser
        parent_dlg.accept()

        prog_dlg = QDialog(self)
        prog_dlg.setWindowTitle("Mise à jour")
        prog_dlg.setFixedSize(380, 120)
        prog_dlg.setWindowFlags(prog_dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(prog_dlg)
        lbl = QLabel("⏳  Téléchargement en cours...")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
        layout.addWidget(lbl)
        bar = QProgressBar()
        bar.setRange(0, 0)
        layout.addWidget(bar)
        prog_dlg.show()

        def do_dl():
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
                urllib.request.urlretrieve(DOWNLOAD_URL, tmp.name)
                tmp.close()
                prog_dlg.close()
                subprocess.Popen([tmp.name])
                QTimer.singleShot(500, self.close)
            except Exception:
                prog_dlg.close()
                webbrowser.open(DOWNLOAD_URL)

        threading.Thread(target=do_dl, daemon=True).start()


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QLabel { border: none; background: transparent; color: #1e293b; }
        QLineEdit { color: #1e293b; background: white; }
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical { background: #f1f5f9; width: 8px; border-radius: 4px; }
        QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    """)

    # High DPI scaling — automatic in PyQt6
    data = load_zones()

    if not is_licensed():
        # Show activation window
        from license import ActivationWindowQt
        act = ActivationWindowQt(data)
        if not act.exec():
            sys.exit(0)

    window = DariaApp(data)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
