from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt
from config import COLORS, ZONE_COLORS, PRIORITY_COLORS, styled_btn
from utils import get_all_reps


class EquipePage(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data     = data
        self.all_reps = get_all_reps(data)
        self.setStyleSheet(f"""
            background-color: {COLORS['bg']};
            QLabel {{ border: none; background: transparent; }}
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']};")
        hdr.setFixedHeight(52)
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Notre Équipe")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        hdr_l.addWidget(title)

        count = QLabel(f"{len(self.all_reps)} représentants")
        count.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; border: none; background: transparent;")
        hdr_l.addWidget(count)
        hdr_l.addStretch()
        layout.addWidget(hdr)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLORS['bg']};")
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(24, 16, 24, 16)
        content_l.setSpacing(0)

        # Group by zone
        zones_seen = {}
        for item in self.all_reps:
            zid = item["zone"]["id"]
            if zid not in zones_seen:
                zones_seen[zid] = {
                    "nom":     item["zone"]["nom"],
                    "couleur": ZONE_COLORS.get(zid, COLORS["accent"]),
                    "reps":    []
                }
            zones_seen[zid]["reps"].append(item["rep"])

        for zid, zinfo in zones_seen.items():
            # Zone header
            zh = QFrame()
            zh.setFixedHeight(36)
            zh.setStyleSheet(f"background-color: {zinfo['couleur']}; border-radius: 6px;")
            zh_l = QHBoxLayout(zh)
            zh_l.setContentsMargins(14, 0, 14, 0)
            zh_lbl = QLabel(f"  {zinfo['nom'].upper()}")
            zh_lbl.setStyleSheet("color: white; font-size: 12px; font-weight: bold; background: transparent; border: none;")
            zh_l.addWidget(zh_lbl)
            content_l.addSpacing(14)
            content_l.addWidget(zh)
            content_l.addSpacing(4)

            for rep in zinfo["reps"]:
                content_l.addWidget(self._rep_row(rep))
                content_l.addSpacing(3)

        content_l.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _rep_row(self, rep):
        card = QFrame()
        card.setObjectName("repCard")
        card.setStyleSheet(f"""
            QFrame#repCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            QFrame#repCard QLabel {{ border: none; background: transparent; }}
        """)
        card_l = QHBoxLayout(card)
        card_l.setContentsMargins(14, 10, 14, 10)
        card_l.setSpacing(8)

        # Left info
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(3)

        # Priority badge + name
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        prio       = rep.get("priorite", 99)
        prio_color = PRIORITY_COLORS.get(prio, "#64748b")
        prio_text  = f"PRIORITÉ {prio}" if prio <= 3 else "AUTRE"

        badge = QLabel(f"  {prio_text}  ")
        badge.setStyleSheet(f"""
            background-color: {prio_color};
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            padding: 2px 4px;
        """)
        badge.setFixedHeight(22)
        top_row.addWidget(badge)

        name_lbl = QLabel(rep["nom"])
        name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: bold; background: transparent;")
        top_row.addWidget(name_lbl)
        top_row.addStretch()
        left_l.addLayout(top_row)

        jours_lbl = QLabel(rep.get("jours", ""))
        jours_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        left_l.addWidget(jours_lbl)

        card_l.addWidget(left)
        card_l.addStretch()

        # Calendar button
        cal_btn = styled_btn("Calendrier", COLORS["green"], height=34, width=110)
        cal_btn.clicked.connect(lambda checked, r=rep: self._open_calendar(r))
        card_l.addWidget(cal_btn)

        return card

    def _open_calendar(self, rep):
        from pages.calendrier import CalendarWindow
        win = CalendarWindow(rep, self)
        win.show()

    def refresh(self):
        pass