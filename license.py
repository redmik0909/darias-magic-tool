import hashlib
import os
import platform
import subprocess
import customtkinter as ctk
from config import C, label, btn

# Licence dans AppData — préservée lors des mises à jour
_APP_DATA    = os.path.join(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))), "DariasMagicTool")
os.makedirs(_APP_DATA, exist_ok=True)
LICENSE_FILE = os.path.join(_APP_DATA, ".license")

# Migration automatique — copie l'ancien .license vers AppData si nécessaire
_OLD_LICENSE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license")
if not os.path.exists(LICENSE_FILE) and os.path.exists(_OLD_LICENSE):
    import shutil
    shutil.copy(_OLD_LICENSE, LICENSE_FILE)
SECRET_SALT  = "darias-magic-tool-2026-xK9#mP"


def get_hardware_id() -> str:
    """Generate a unique ID based on this machine's hardware."""
    parts = []

    # Machine name
    parts.append(platform.node())

    # Windows: get CPU ID via WMIC
    try:
        result = subprocess.check_output(
            "wmic cpu get ProcessorId", shell=True, stderr=subprocess.DEVNULL
        ).decode().strip().split("\n")
        cpu_id = [l.strip() for l in result if l.strip() and "ProcessorId" not in l]
        if cpu_id:
            parts.append(cpu_id[0])
    except Exception:
        pass

    # Windows: get Motherboard serial
    try:
        result = subprocess.check_output(
            "wmic baseboard get SerialNumber", shell=True, stderr=subprocess.DEVNULL
        ).decode().strip().split("\n")
        mb = [l.strip() for l in result if l.strip() and "SerialNumber" not in l]
        if mb:
            parts.append(mb[0])
    except Exception:
        pass

    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16].upper()


def generate_license_key(hardware_id: str) -> str:
    """Generate the valid license key for a given hardware ID."""
    raw = f"{SECRET_SALT}:{hardware_id}"
    h   = hashlib.sha256(raw.encode()).hexdigest().upper()
    # Format: XXXX-XXXX-XXXX-XXXX
    return f"{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def is_licensed() -> bool:
    """Check if this machine has a valid saved license."""
    if not os.path.exists(LICENSE_FILE):
        return False
    try:
        with open(LICENSE_FILE, "r") as f:
            saved_key = f.read().strip()
        hw_id       = get_hardware_id()
        valid_key   = generate_license_key(hw_id)
        return saved_key == valid_key
    except Exception:
        return False


def save_license(key: str) -> bool:
    """Validate and save a license key. Returns True if valid."""
    hw_id     = get_hardware_id()
    valid_key = generate_license_key(hw_id)
    if key.strip().upper() == valid_key:
        with open(LICENSE_FILE, "w") as f:
            f.write(key.strip().upper())
        return True
    return False


# ── Activation Window ──────────────────────────────────────────────────────────
class ActivationWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Activation — Daria's Magic Tool")
        self.geometry("480x340")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#1e3a5f", corner_radius=0)
        header.pack(fill="x")
        label(header, "Daria's Magic Tool", size=18, weight="bold", color="#ffffff").pack(pady=(16, 2))
        label(header, "Activation requise", size=12, color="#93c5fd").pack(pady=(0, 14))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=24)

        label(body,
              "Ce logiciel est protege par licence.\nEntrez votre cle d'activation pour continuer.",
              size=12, color=C["text_muted"], justify="center").pack(pady=(0, 20))

        # Hardware ID display
        hw_id = get_hardware_id()
        hw_frame = ctk.CTkFrame(body, fg_color=C["surface2"], corner_radius=6,
                                border_width=1, border_color=C["border"])
        hw_frame.pack(fill="x", pady=(0, 16))
        label(hw_frame, "ID de cette machine :", size=11, color=C["text_muted"]).pack(anchor="w", padx=12, pady=(8, 2))

        id_row = ctk.CTkFrame(hw_frame, fg_color="transparent")
        id_row.pack(fill="x", padx=12, pady=(0, 8))

        label(id_row, hw_id, size=13, weight="bold", color=C["accent"]).pack(side="left")

        def copy_hw_id():
            self.clipboard_clear()
            self.clipboard_append(hw_id)
            copy_btn.configure(text="Copie!", fg_color=C["green"], hover_color=C["green_h"])
            self.after(1500, lambda: copy_btn.configure(text="Copier", fg_color=C["surface"], hover_color=C["border"]))

        copy_btn = ctk.CTkButton(
            id_row, text="Copier", width=70, height=26,
            corner_radius=4, fg_color=C["surface"],
            hover_color=C["border"], font=ctk.CTkFont(size=11),
            text_color=C["text_muted"], border_width=1,
            border_color=C["border"], command=copy_hw_id
        )
        copy_btn.pack(side="left", padx=(12, 0))

        # Key entry
        label(body, "Cle d'activation :", size=12, color=C["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.key_entry = ctk.CTkEntry(
            body, placeholder_text="XXXX-XXXX-XXXX-XXXX",
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=6, fg_color=C["surface"],
            border_color=C["border"], justify="center"
        )
        self.key_entry.pack(fill="x", pady=(0, 8))
        self.key_entry.bind("<Return>", lambda e: self._activate())

        self.status_var = ctk.StringVar(value="")
        ctk.CTkLabel(body, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11),
                     text_color=C["red"]).pack(pady=(0, 12))

        btn(body, "Activer", self._activate,
            width=200, height=40, color=C["accent"], hover=C["accent_h"]).pack()

    def _activate(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status_var.set("Entrez une cle d'activation.")
            return
        if save_license(key):
            self.destroy()
            self.on_success()
        else:
            self.status_var.set("Cle invalide pour cette machine.")
            self.key_entry.configure(border_color=C["red"])

    def _on_close(self):
        try:
            self.status_var.set("Vous devez activer le logiciel pour continuer.")
        except Exception:
            pass