import config  # noqa — must be imported first (sets DPI + theme)
import customtkinter as ctk
import urllib.request
import threading
from config import C, label
from utils import load_zones
from pages.accueil import AccueilPage
from pages.recherche import RecherchePage
from pages.equipe import EquipePage
from pages.route import RoutePage
from license import is_licensed, ActivationWindow

CURRENT_VERSION = "2.3.6"
VERSION_URL     = "https://raw.githubusercontent.com/redmik0909/darias-magic-tool/main/version.txt"
DOWNLOAD_URL    = "https://github.com/redmik0909/darias-magic-tool/releases/latest/download/DariasMagicTool-Setup-latest.exe"


def _check_google_setup():
    """Check if Google credentials password is in keyring."""
    try:
        import keyring
        pwd = keyring.get_password("DariasMagicTool", "google_creds_password")
        if not pwd:
            return False
        from crypto_utils import decrypt_credentials
        data = decrypt_credentials()
        return data is not None
    except Exception:
        return False


def _show_google_setup(app):
    """Show Google credentials setup window on first launch."""
    from crypto_utils import decrypt_with_password
    import keyring

    dialog = ctk.CTkToplevel(app)
    dialog.title("Configuration Google Calendar")
    dialog.geometry("460x300")
    dialog.configure(fg_color=C["bg"])
    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()
    dialog.grab_set()
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    hdr = ctk.CTkFrame(dialog, fg_color="#1e3a5f", corner_radius=0)
    hdr.pack(fill="x")
    label(hdr, "  🔐  Configuration requise",
          size=14, weight="bold", color="#ffffff").pack(side="left", pady=14, padx=8)

    label(dialog,
          "Premier lancement - entrez le mot de passe pour activer Google Calendar.",
          size=12, color=C["text"], justify="center").pack(pady=(20, 4))
    label(dialog,
          "Contactez votre administrateur si vous ne l avez pas.",
          size=11, color=C["text_muted"]).pack(pady=(0, 16))

    pwd_entry = ctk.CTkEntry(dialog, placeholder_text="Mot de passe...",
                              show="*", height=40, width=300,
                              font=ctk.CTkFont(size=13))
    pwd_entry.pack(pady=(0, 8))
    pwd_entry.bind("<Return>", lambda e: confirm())
    pwd_entry.focus()

    err_var = ctk.StringVar(value="")
    ctk.CTkLabel(dialog, textvariable=err_var,
                 font=ctk.CTkFont(size=11),
                 text_color=C["red"]).pack()

    def confirm():
        pwd = pwd_entry.get().strip()
        if not pwd:
            err_var.set("Entrez un mot de passe.")
            return
        data = decrypt_with_password(pwd)
        if not data:
            err_var.set("❌  Mot de passe incorrect. Réessayez.")
            pwd_entry.delete(0, "end")
            return
        keyring.set_password("DariasMagicTool", "google_creds_password", pwd)
        dialog.destroy()

    btn(dialog, "✅  Confirmer", confirm,
        width=200, height=40, color=C["green"], hover=C["green_h"]).pack(pady=16)


class DariaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Daria's Magic Tool")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.minsize(700, 500)
        self.after(100, lambda: self.state("zoomed"))
        self.configure(fg_color=C["bg"])
        self.data = load_zones()

        # Check licence before showing app
        if not is_licensed():
            self.withdraw()  # Hide main window
            ActivationWindow(self, self._on_activated)
        else:
            self._build_ui()

    def _on_activated(self):
        """Called after successful activation."""
        self.deiconify()  # Show main window
        self._build_ui()

    def _build_ui(self):
        # ── Sidebar ───────────────────────────────────────────────────────────
        # Responsive sidebar — 15% of screen width, min 160, max 220
        sw = self.winfo_screenwidth()
        sidebar_w = max(160, min(220, int(sw * 0.15)))
        self.sidebar = ctk.CTkFrame(self, fg_color="#1e3a5f", corner_radius=0, width=sidebar_w)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo = ctk.CTkFrame(self.sidebar, fg_color="#16305a", corner_radius=0)
        logo.pack(fill="x")

        ctk.CTkLabel(logo, text="✨",
                     font=ctk.CTkFont(size=34),
                     text_color="#ffffff").pack(pady=(20, 0))
        label(logo, "Daria's Magic Tool",
              size=15, weight="bold", color="#ffffff").pack(pady=(6, 2))
        label(logo, "by RevolvIT",
              size=11, color="#93c5fd").pack(pady=(0, 18))

        # Divider
        ctk.CTkFrame(self.sidebar, fg_color="#2a4a7f", height=1).pack(fill="x")

        # Section label
        label(self.sidebar, "  NAVIGATION",
              size=9, color="#4a6a9f").pack(anchor="w", padx=14, pady=(16, 4))

        # Nav
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10)

        self.nav_buttons = {}
        nav_items = [
            ("accueil",   "🏠", "Accueil"),
            ("recherche", "🔍", "Recherche"),
            ("equipe",    "👥", "Équipe"),
            ("route",     "🗺", "Route"),
        ]
        for key, icon, text in nav_items:
            row = ctk.CTkFrame(nav_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            b = ctk.CTkButton(
                row,
                text=f"   {icon}   {text}",
                width=sidebar_w - 24, height=max(36, int(self.winfo_screenheight() * 0.055)),
                corner_radius=10, anchor="w",
                fg_color="transparent",
                hover_color="#2a4a7f",
                font=ctk.CTkFont(size=max(11, int(sw * 0.007))),
                text_color="#bfdbfe",
                command=lambda k=key: self._switch_tab(k)
            )
            b.pack(fill="x")
            self.nav_buttons[key] = b

        # Bottom info
        ctk.CTkFrame(self.sidebar, fg_color="#2a4a7f", height=1).pack(side="bottom", fill="x")
        bottom = ctk.CTkFrame(self.sidebar, fg_color="#16305a")
        bottom.pack(side="bottom", fill="x")
        label(bottom, "RevolvIT", size=11, weight="bold", color="#ffffff").pack(anchor="w", padx=14, pady=(10,0))
        label(bottom, f"v{CURRENT_VERSION}", size=10, color="#4a6a9f").pack(anchor="w", padx=14, pady=(0,10))

        # ── Content ───────────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {
            "accueil":   AccueilPage(self.content),
            "recherche": RecherchePage(self.content, self.data),
            "equipe":    EquipePage(self.content, self.data),
            "route":     RoutePage(self.content, self.data),
        }
        self._finish_build()

    def _finish_build(self):
        self._switch_tab("accueil")

        # Check Google credentials on first launch
        if not _check_google_setup():
            self.after(500, lambda: _show_google_setup(self))

        # Check for updates in background
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self):
        try:
            req = urllib.request.Request(
                VERSION_URL,
                headers={"User-Agent": "DariasMagicTool"}
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                latest = r.read().decode().strip()
            if latest != CURRENT_VERSION:
                self.after(0, self._show_update_popup, latest)
        except Exception:
            pass  # Silently ignore if no internet or server down

    def _show_update_popup(self, latest_version):
        import webbrowser
        popup = ctk.CTkToplevel(self)
        popup.title("Mise à jour disponible")
        popup.geometry("420x220")
        popup.configure(fg_color=C["bg"])
        popup.attributes("-topmost", True)
        popup.lift()
        popup.focus_force()
        popup.grab_set()

        # Header
        hdr = ctk.CTkFrame(popup, fg_color="#1e3a5f", corner_radius=0)
        hdr.pack(fill="x")
        label(hdr, "  🔄  Mise à jour disponible",
              size=14, weight="bold", color="#ffffff").pack(side="left", pady=14, padx=4)

        label(popup, f"Une nouvelle version est disponible : v{latest_version}",
              size=13, color=C["text"]).pack(pady=(16, 4))
        label(popup, f"Vous utilisez actuellement la version v{CURRENT_VERSION}",
              size=11, color=C["text_muted"]).pack(pady=(0, 16))

        row = ctk.CTkFrame(popup, fg_color="transparent")
        row.pack()

        ctk.CTkButton(row, text="Télécharger la mise à jour",
                      width=200, height=38, corner_radius=6,
                      fg_color=C["green"], hover_color=C["green_h"],
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=lambda: [webbrowser.open(DOWNLOAD_URL), popup.destroy()]
                      ).pack(side="left", padx=6)

        ctk.CTkButton(row, text="Plus tard",
                      width=100, height=38, corner_radius=6,
                      fg_color=C["surface2"], hover_color=C["border"],
                      font=ctk.CTkFont(size=12),
                      text_color=C["text_muted"],
                      command=popup.destroy
                      ).pack(side="left", padx=6)

    def _switch_tab(self, tab):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[tab].pack(fill="both", expand=True)

        for key, b in self.nav_buttons.items():
            if key == tab:
                b.configure(fg_color="#2563eb", text_color="white",
                            font=ctk.CTkFont(size=13, weight="bold"))
            else:
                b.configure(fg_color="transparent", text_color="#bfdbfe",
                            font=ctk.CTkFont(size=13))

        # Refresh data when switching tabs
        page = self.pages[tab]
        if hasattr(page, "refresh"):
            page.refresh()


if __name__ == "__main__":
    app = DariaApp()
    app.mainloop()
