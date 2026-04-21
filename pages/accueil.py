from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer
from datetime import datetime

JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_FR  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

COLORS = {
    "bg":       "#f8fafc",
    "surface":  "#ffffff",
    "border":   "#e2e8f0",
    "text":     "#1e293b",
    "muted":    "#64748b",
    "dim":      "#94a3b8",
    "accent":   "#2563eb",
    "purple":   "#7c3aed",
}


class AccueilPage(QWidget):
    def __init__(self, data=None):
        super().__init__()
        self.setStyleSheet(f"background-color: {COLORS['bg']};")
        self._build()

        # Update clock every minute
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(60000)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        # Center container
        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center.setFixedWidth(600)
        center_l = QVBoxLayout(center)
        center_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_l.setSpacing(8)

        # Emoji
        emoji = QLabel("✨")
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji.setStyleSheet(f"color: {COLORS['accent']}; font-size: 72px; background: transparent;")
        center_l.addWidget(emoji)

        # Greeting
        greeting = QLabel("Bonjour Daria!")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greeting.setStyleSheet(f"color: {COLORS['text']}; font-size: 48px; font-weight: bold; background: transparent;")
        center_l.addWidget(greeting)

        sub = QLabel("Ton twin te souhaite un bon shift 💪")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {COLORS['muted']}; font-size: 22px; background: transparent;")
        center_l.addWidget(sub)

        center_l.addSpacing(24)

        # Date & time card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(40, 16, 40, 16)
        card_l.setSpacing(4)

        now   = datetime.now()
        jour  = JOURS_FR[now.weekday()]
        date  = f"{jour} {now.day} {MOIS_FR[now.month]} {now.year}"

        self.date_lbl = QLabel(date)
        self.date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-size: 16px; background: transparent; border: none;")
        card_l.addWidget(self.date_lbl)

        self.time_lbl = QLabel(now.strftime("%H:%M"))
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet(f"color: {COLORS['purple']}; font-size: 48px; font-weight: bold; background: transparent; border: none;")
        card_l.addWidget(self.time_lbl)

        center_l.addWidget(card)
        center_l.addSpacing(24)

        # Tip
        tip = QLabel("👉  Utilise l'onglet Recherche pour trouver le bon technicien")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(f"color: {COLORS['dim']}; font-size: 14px; background: transparent;")
        center_l.addWidget(tip)

        layout.addWidget(center)

    def _update_time(self):
        now  = datetime.now()
        jour = JOURS_FR[now.weekday()]
        self.date_lbl.setText(f"{jour} {now.day} {MOIS_FR[now.month]} {now.year}")
        self.time_lbl.setText(now.strftime("%H:%M"))

    def refresh(self):
        self._update_time()