import customtkinter as ctk
import ctypes

# ── DPI Fix Windows ────────────────────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Theme ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
ctk.deactivate_automatic_dpi_awareness()

# ── Colour palette ─────────────────────────────────────────────────────────────
C = {
    "bg":         "#f0f4f8",
    "surface":    "#ffffff",
    "surface2":   "#e8edf2",
    "border":     "#cfd8e3",
    "accent":     "#2563eb",
    "accent_h":   "#1d4ed8",
    "green":      "#16a34a",
    "green_h":    "#15803d",
    "red":        "#dc2626",
    "orange":     "#d97706",
    "purple":     "#7c3aed",
    "text":       "#1e293b",
    "text_muted": "#64748b",
    "text_dim":   "#94a3b8",
    "p1":         "#16a34a",
    "p2":         "#d97706",
    "p3":         "#dc2626",
    "ov":         "#64748b",
}

ZONE_COLORS = {
    "rive_nord":        "#2563eb",
    "montreal_rive_sud":"#16a34a",
    "lanaudiere_tr":    "#dc2626",
    "gatineau":         "#7c3aed",
    "quebec":           "#d97706",
    "saguenay":         "#6e40c9",
    "sherbrooke_beauce":"#545d68",
    "home_depot":       "#bf4b00",
}

PRIORITY_LABELS = {
    1:  ("PRIORITÉ 1", "#16a34a"),
    2:  ("PRIORITÉ 2", "#d97706"),
    3:  ("PRIORITÉ 3", "#dc2626"),
    99: ("OVERFLOW",   "#64748b"),
}

JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR  = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

# ── UI shortcut helpers ────────────────────────────────────────────────────────
def label(parent, text, size=13, weight="normal", color=None, **kwargs):
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=size, weight=weight),
        text_color=color or C["text"],
        **kwargs
    )

def btn(parent, text, command, width=120, height=36, color=None, hover=None, **kwargs):
    return ctk.CTkButton(
        parent, text=text, command=command,
        width=width, height=height,
        fg_color=color or C["accent"],
        hover_color=hover or C["accent_h"],
        font=ctk.CTkFont(size=12, weight="bold"),
        corner_radius=6,
        **kwargs
    )