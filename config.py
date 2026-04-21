# config.py — Constantes UI pour PyQt6
# Plus besoin de DPI fix, CTk, label(), btn() — PyQt6 gère tout nativement

COLORS = {
    "bg":          "#f8fafc",
    "surface":     "#ffffff",
    "surface2":    "#f1f5f9",
    "border":      "#e2e8f0",
    "accent":      "#2563eb",
    "accent_h":    "#1d4ed8",
    "green":       "#16a34a",
    "green_h":     "#15803d",
    "red":         "#dc2626",
    "orange":      "#d97706",
    "purple":      "#7c3aed",
    "text":        "#1e293b",
    "text_muted":  "#64748b",
    "text_dim":    "#94a3b8",
    "p1":          "#16a34a",
    "p2":          "#d97706",
    "p3":          "#dc2626",
    "sidebar":     "#1e3a5f",
    "sidebar_dark":"#16305a",
    "sidebar_div": "#2a4a7f",
}

ZONE_COLORS = {
    "rive_nord":         "#2563eb",
    "montreal_rive_sud": "#16a34a",
    "lanaudiere_tr":     "#dc2626",
    "gatineau":          "#7c3aed",
    "quebec":            "#d97706",
    "saguenay":          "#6e40c9",
    "sherbrooke_beauce": "#545d68",
    "home_depot":        "#bf4b00",
}

PRIORITY_COLORS = {
    1:  "#16a34a",
    2:  "#d97706",
    3:  "#dc2626",
    99: "#64748b",
}

JOURS_FR = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
MOIS_FR  = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def styled_btn(text, color=None, text_color="#ffffff", height=36, width=None):
    """Create a styled QPushButton — import PyQt6 locally to avoid circular imports."""
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton(text)
    bg  = color or COLORS["accent"]
    if width:
        btn.setFixedWidth(width)
    btn.setFixedHeight(height)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: {text_color};
            border: none;
            border-radius: 6px;
            padding: 0 16px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {_darken(bg)};
        }}
        QPushButton:disabled {{
            background-color: #94a3b8;
            color: white;
        }}
    """)
    return btn


def _darken(hex_color, factor=0.9):
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"
    except Exception:
        return hex_color


def card_style(bg=None, border=None, radius=8):
    """Return QFrame stylesheet for a card."""
    bg     = bg or COLORS["surface"]
    border = border or COLORS["border"]
    return f"""
        QFrame {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}
    """