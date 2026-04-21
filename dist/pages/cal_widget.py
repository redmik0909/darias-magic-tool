"""
cal_widget.py — Widget calendrier Google partagé (PyQt6)
"""
import calendar
import threading
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QDialog,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

from config import COLORS, MOIS_FR, JOURS_FR, styled_btn
from google_cal import get_events_for_month, find_calendar_by_name, format_time

SKIP_KEYWORDS  = ["PAS DE RDV", "INDISPONIBLE", "CONGE", "CONGÉ", "FÉRIÉ", "FERIE", "EVITER", "AVOID"]
BLOCK_KEYWORDS = ["PAS DE RDV", "INDISPONIBLE", "CONGE", "CONGÉ", "FÉRIÉ", "FERIE"]
AVOID_KEYWORDS = ["EVITER", "AVOID"]


def is_real_rdv(e):
    if any(x in e.get("summary", "").upper() for x in SKIP_KEYWORDS):
        return False
    return bool(e.get("location", "").strip()) or "|" in e.get("summary", "")

def is_blocked_day(events):
    has_block = any(any(x in e.get("summary", "").upper() for x in BLOCK_KEYWORDS) for e in events)
    has_rdv   = any(is_real_rdv(e) for e in events)
    return has_block and not has_rdv

def get_avoided_slots(events):
    avoided = set()
    for e in events:
        if any(x in e.get("summary", "").upper() for x in AVOID_KEYWORDS):
            h = format_time(e.get("start", ""))
            if h:
                avoided.add(h[:2])
    return avoided

def find_cal_id(rep):
    keywords = [rep["nom"].split()[0]]
    if len(rep["nom"].split()) > 1:
        keywords.append(rep["nom"].split()[1])
    cal_field = rep.get("google_calendar", "")
    if cal_field:
        for p in [x.strip() for x in cal_field.replace("/", ",").split(",")]:
            if p and p.upper() not in ["RDV", "MTL", "TR"]:
                keywords.append(p[:10])
    for kw in keywords:
        cal_id, _ = find_calendar_by_name(kw)
        if cal_id:
            return cal_id
    return None


# ── Fetch thread ───────────────────────────────────────────────────────────────
class CalFetchThread(QThread):
    done = pyqtSignal(dict)

    def __init__(self, cal_id, year, month):
        super().__init__()
        self.cal_id = cal_id
        self.year   = year
        self.month  = month

    def run(self):
        try:
            events = get_events_for_month(self.cal_id, self.year, self.month)
            self.done.emit(events)
        except Exception:
            self.done.emit({})


# ── Day popup ──────────────────────────────────────────────────────────────────
def show_day_popup(parent, rep, date_key, events):
    day_parts = date_key.split("-")
    day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]} {day_parts[0]}"
    real_rdv  = [e for e in events if is_real_rdv(e)]

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"RDV - {day_fmt}")
    dlg.setMinimumSize(500, 400)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # Header
    hdr = QFrame()
    hdr.setStyleSheet(f"background-color: {COLORS['sidebar']}; border: none;")
    hdr.setFixedHeight(52)
    hdr_l = QHBoxLayout(hdr)
    hdr_l.setContentsMargins(12, 0, 12, 0)

    hdr_title = QLabel(f"  {day_fmt} - {rep['nom']}")
    hdr_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
    hdr_l.addWidget(hdr_title)
    hdr_l.addStretch()

    count_lbl = QLabel(f"{len(real_rdv)} RDV")
    count_lbl.setStyleSheet("color: #93c5fd; font-size: 12px; background: transparent;")
    hdr_l.addWidget(count_lbl)
    layout.addWidget(hdr)

    # Content
    if not real_rdv:
        empty = QLabel("Aucun RDV ce jour — journée libre!")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(f"color: {COLORS['green']}; font-size: 13px; padding: 40px;")
        layout.addWidget(empty)
    else:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        content.setStyleSheet(f"background-color: {COLORS['bg']};")
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(12, 12, 12, 12)
        content_l.setSpacing(8)

        for e in real_rdv:
            card = QFrame()
            card.setStyleSheet(f"background-color: {COLORS['surface2']}; border-radius: 6px;")
            card_l = QVBoxLayout(card)
            card_l.setContentsMargins(12, 8, 12, 8)
            card_l.setSpacing(4)

            time_str = format_time(e["start"])
            top_row  = QHBoxLayout()

            time_lbl = QLabel(f" {time_str} ")
            time_lbl.setStyleSheet(f"""
                background-color: {COLORS['accent']};
                color: white;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 6px;
            """)
            time_lbl.setFixedHeight(24)
            top_row.addWidget(time_lbl)

            name_lbl = QLabel(e.get("summary", "Sans titre"))
            name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: bold; background: transparent;")
            name_lbl.setWordWrap(True)
            top_row.addWidget(name_lbl)
            top_row.addStretch()
            card_l.addLayout(top_row)

            if e.get("location"):
                loc_lbl = QLabel(f"📍 {e['location']}")
                loc_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
                loc_lbl.setWordWrap(True)
                card_l.addWidget(loc_lbl)

            content_l.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    # Close button
    close_btn = styled_btn("Fermer", COLORS["surface2"], COLORS["text_muted"], height=34, width=120)
    close_btn.setStyleSheet(close_btn.styleSheet() + f"border: 1px solid {COLORS['border']};")
    close_btn.clicked.connect(dlg.accept)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(close_btn)
    btn_row.addStretch()

    btn_widget = QWidget()
    btn_widget.setStyleSheet(f"background-color: {COLORS['bg']}; border: none;")
    btn_widget.setLayout(btn_row)
    btn_widget.setFixedHeight(52)
    layout.addWidget(btn_widget)

    dlg.exec()


# ── Google Calendar Widget ─────────────────────────────────────────────────────
class GoogleCalWidget(QWidget):
    def __init__(self, parent=None, rep=None, on_day_click=None, max_rdv=5):
        super().__init__(parent)
        self.rep          = rep
        self.on_day_click = on_day_click
        self.max_rdv      = max_rdv
        self.cal_id       = None
        self.cal_date     = datetime.today().replace(day=1)
        self.month_events = {}
        self.selected     = None
        self.view_mode    = "calendar"
        self.fetch_thread = None
        self.setStyleSheet(f"""
            QWidget {{ background-color: {COLORS['surface']}; }}
            QLabel {{ border: none; background: transparent; color: {COLORS['text']}; }}
            QFrame {{ border: none; background: transparent; }}
        """)
        self._build()

    def _build(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']};")
        hdr.setFixedHeight(50)
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(16, 0, 12, 0)

        title = QLabel(f"Calendrier — {self.rep['nom']}" if self.rep else "Calendrier")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(title)
        hdr_l.addStretch()

        # Nav buttons
        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedSize(32, 28)
        self.prev_btn.setStyleSheet(self._nav_btn_style())
        self.prev_btn.clicked.connect(lambda: self._change_month(-1))
        hdr_l.addWidget(self.prev_btn)

        self.nav_lbl = QLabel("")
        self.nav_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: bold; background: transparent; min-width: 140px;")
        self.nav_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_l.addWidget(self.nav_lbl)

        self.next_btn = QPushButton(">")
        self.next_btn.setFixedSize(32, 28)
        self.next_btn.setStyleSheet(self._nav_btn_style())
        self.next_btn.clicked.connect(lambda: self._change_month(1))
        hdr_l.addWidget(self.next_btn)

        self.main_layout.addWidget(hdr)

        # Toggle bar
        toggle = QFrame()
        toggle.setStyleSheet(f"background-color: {COLORS['surface2']}; border-bottom: 1px solid {COLORS['border']};")
        toggle.setFixedHeight(46)
        toggle_l = QHBoxLayout(toggle)
        toggle_l.setContentsMargins(8, 6, 8, 6)
        toggle_l.setSpacing(4)

        self.btn_cal = QPushButton("📅  Calendrier")
        self.btn_cal.setFixedSize(130, 30)
        self.btn_cal.setStyleSheet(self._toggle_style(True))
        self.btn_cal.clicked.connect(self._to_calendar)

        self.btn_lst = QPushButton("☰  Liste")
        self.btn_lst.setFixedSize(100, 30)
        self.btn_lst.setStyleSheet(self._toggle_style(False))
        self.btn_lst.clicked.connect(self._to_list)

        toggle_l.addWidget(self.btn_cal)
        toggle_l.addWidget(self.btn_lst)
        toggle_l.addStretch()
        self.main_layout.addWidget(toggle)

        # Content area
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        loading = QLabel("Chargement du calendrier...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        self.content_layout.addWidget(loading)

        self.main_layout.addWidget(self.content)
        self._update_nav()

    def _nav_btn_style(self):
        return f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_h']}; }}
        """

    def _toggle_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background-color: {COLORS['accent']};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['border']}; }}
        """

    def load(self, cal_id):
        # Always call from main thread via QTimer
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._load_safe(cal_id))

    def _load_safe(self, cal_id):
        self.cal_id = cal_id
        self._update_nav()
        self._fetch()

    def _fetch(self):
        if not self.cal_id:
            return
        self._show_loading()
        self.fetch_thread = CalFetchThread(self.cal_id, self.cal_date.year, self.cal_date.month)
        self.fetch_thread.done.connect(self._on_fetched)
        self.fetch_thread.start()

    def _on_fetched(self, events):
        self.month_events = events
        self._render()

    def _show_loading(self):
        self._clear_content()
        loading = QLabel("Chargement...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        self.content_layout.addWidget(loading)

    def _update_nav(self):
        y, m = self.cal_date.year, self.cal_date.month
        self.nav_lbl.setText(f"{MOIS_FR[m]} {y}")

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _to_calendar(self):
        self.view_mode = "calendar"
        self.btn_cal.setStyleSheet(self._toggle_style(True))
        self.btn_lst.setStyleSheet(self._toggle_style(False))
        self._render()

    def _to_list(self):
        self.view_mode = "list"
        self.btn_cal.setStyleSheet(self._toggle_style(False))
        self.btn_lst.setStyleSheet(self._toggle_style(True))
        self._render()

    def _change_month(self, delta):
        m, y = self.cal_date.month + delta, self.cal_date.year
        if m == 0:  m, y = 12, y - 1
        if m == 13: m, y = 1,  y + 1
        self.cal_date     = self.cal_date.replace(year=y, month=m, day=1)
        self.month_events = {}
        self._update_nav()
        if self.cal_id:
            self._fetch()
        else:
            self._render()

    def _render(self):
        self._clear_content()
        if self.view_mode == "calendar":
            self._render_grid()
        else:
            self._render_list()

    # ── Grid view ──────────────────────────────────────────────────────────────
    def _render_grid(self):
        y, m  = self.cal_date.year, self.cal_date.month
        today = datetime.today()
        _, days_in_month = calendar.monthrange(y, m)
        first_col = (datetime(y, m, 1).weekday() + 1) % 7

        # Day headers
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet(f"background-color: {COLORS['surface2']};")
        hdr_layout = QHBoxLayout(hdr_widget)
        hdr_layout.setContentsMargins(4, 4, 4, 4)
        hdr_layout.setSpacing(2)
        for j in JOURS_FR:
            lbl = QLabel(j)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; font-weight: bold; background: transparent;")
            hdr_layout.addWidget(lbl)
        self.content_layout.addWidget(hdr_widget)

        # Grid
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setSpacing(2)

        num_rows = ((days_in_month + first_col - 1) // 7) + 1
        for c in range(7):
            grid_layout.setColumnStretch(c, 1)
        for r in range(num_rows):
            grid_layout.setRowStretch(r, 1 if r < num_rows - 1 else 0)
            grid_layout.setRowMinimumHeight(r, 100)

        row, col = 0, first_col

        for day in range(1, days_in_month + 1):
            date_key   = f"{y}-{m:02d}-{day:02d}"
            day_dt     = datetime(y, m, day)
            is_today   = (today.year == y and today.month == m and today.day == day)
            is_past    = day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0)
            is_sel     = self.selected == date_key
            all_events = self.month_events.get(date_key, [])
            rdv_list   = [e for e in all_events if is_real_rdv(e)]
            blocked    = is_blocked_day(all_events)
            is_full    = len(rdv_list) >= self.max_rdv

            if is_sel:
                bg, border = "#dbeafe", COLORS["accent"]
            elif is_today:
                bg, border = "#f0f9ff", COLORS["accent"]
            elif is_past:
                bg, border = "#f1f5f9", COLORS["border"]
            elif blocked:
                bg, border = "#e2e8f0", "#94a3b8"
            elif is_full:
                bg, border = "#fef2f2", COLORS["red"]
            else:
                bg, border = COLORS["surface"], COLORS["border"]

            cell = QFrame()
            cell.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 6px;
                }}
            """)
            cell_l = QVBoxLayout(cell)
            cell_l.setContentsMargins(4, 3, 4, 3)
            cell_l.setSpacing(1)

            # Day number
            day_color = COLORS["accent"] if (is_today or is_sel) else (COLORS["text_dim"] if is_past else COLORS["text"])
            day_lbl   = QLabel(str(day))
            day_lbl.setStyleSheet(f"color: {day_color}; font-size: 11px; font-weight: bold; background: transparent;")
            cell_l.addWidget(day_lbl)

            if blocked and not is_past:
                blocked_lbl = QLabel("🚫")
                blocked_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                blocked_lbl.setStyleSheet("background: transparent; font-size: 9px;")
                cell_l.addWidget(blocked_lbl)
            elif rdv_list and not is_past:
                for rdv in rdv_list[:2]:
                    start_h = format_time(rdv.get("start", ""))
                    summary = rdv.get("summary", "")
                    name_s  = summary.split("|")[1].strip() if "|" in summary else summary.strip()
                    loc     = rdv.get("location", "")
                    addr_s  = loc.split(",")[0][:14] if loc else ""

                    chip_color = COLORS["red"] if is_full else COLORS["green"]
                    chip = QFrame()
                    chip.setStyleSheet(f"background-color: white; border: 1px solid {chip_color}; border-radius: 3px;")
                    chip_l = QVBoxLayout(chip)
                    chip_l.setContentsMargins(3, 2, 3, 2)
                    chip_l.setSpacing(1)

                    if start_h:
                        time_lbl = QLabel(start_h)
                        time_lbl.setStyleSheet(f"""
                            background-color: {chip_color};
                            color: white;
                            font-size: 8px;
                            font-weight: bold;
                            border-radius: 2px;
                            padding: 1px 3px;
                        """)
                        time_lbl.setFixedHeight(16)
                        chip_l.addWidget(time_lbl)

                    name_lbl = QLabel(name_s)
                    name_lbl.setWordWrap(True)
                    name_lbl.setStyleSheet("color: #1e293b; font-size: 9px; font-weight: bold; background: transparent; border: none;")
                    chip_l.addWidget(name_lbl)

                    if addr_s:
                        addr_lbl = QLabel(f"📍 {addr_s}")
                        addr_lbl.setStyleSheet("color: #64748b; font-size: 8px; background: transparent; border: none;")
                        chip_l.addWidget(addr_lbl)

                    cell_l.addWidget(chip)

                if len(rdv_list) > 2:
                    more = QLabel(f"+ {len(rdv_list)-2}")
                    more.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 8px; background: transparent;")
                    cell_l.addWidget(more)

            elif not is_past and not blocked:
                free_lbl = QLabel("Libre")
                free_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 8px; background: transparent;")
                cell_l.addWidget(free_lbl)

            cell_l.addStretch()

            if not is_past:
                cell.mousePressEvent = lambda e, dk=date_key: self._on_click(dk)
                cell.setCursor(Qt.CursorShape.PointingHandCursor)

            grid_layout.addWidget(cell, row, col)

            col += 1
            if col == 7:
                col = 0
                row += 1

        self.content_layout.addWidget(grid_widget, stretch=1)

    # ── List view ──────────────────────────────────────────────────────────────
    def _render_list(self):
        y, m  = self.cal_date.year, self.cal_date.month
        today = datetime.today()
        _, days_in_month = calendar.monthrange(y, m)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLORS['bg']};")
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(8, 8, 8, 8)
        content_l.setSpacing(6)

        for day in range(1, days_in_month + 1):
            date_key   = f"{y}-{m:02d}-{day:02d}"
            day_dt     = datetime(y, m, day)
            sun_wd     = (day_dt.weekday() + 1) % 7
            is_today   = (today.year == y and today.month == m and today.day == day)
            is_past    = day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0)
            is_sel     = self.selected == date_key
            all_events = self.month_events.get(date_key, [])
            rdv_list   = [e for e in all_events if is_real_rdv(e)]
            blocked    = is_blocked_day(all_events)
            is_full    = len(rdv_list) >= self.max_rdv

            if is_past or blocked:
                continue

            if is_sel:
                bg, border, bw = "#dbeafe", COLORS["accent"], "2px"
            elif is_today:
                bg, border, bw = "#f0f9ff", COLORS["accent"], "2px"
            elif is_full:
                bg, border, bw = "#fef2f2", COLORS["red"], "1px"
            else:
                bg, border, bw = COLORS["surface"], COLORS["border"], "1px"

            card = QFrame()
            card.setStyleSheet(f"background-color: {bg}; border: {bw} solid {border}; border-radius: 10px;")
            card_l = QVBoxLayout(card)
            card_l.setContentsMargins(14, 10, 14, 10)
            card_l.setSpacing(6)

            # Day header
            day_hdr = QHBoxLayout()
            jour_nom  = JOURS_FR[sun_wd]
            day_color = COLORS["accent"] if (is_today or is_sel) else COLORS["text"]
            day_title = QLabel(f"{jour_nom}  {day} {MOIS_FR[m]}")
            day_title.setStyleSheet(f"color: {day_color}; font-size: 14px; font-weight: bold; background: transparent;")
            day_hdr.addWidget(day_title)
            day_hdr.addStretch()

            if is_full:
                badge_bg, badge_txt = COLORS["red"], f"Complet · {len(rdv_list)} RDV"
            elif rdv_list:
                badge_bg, badge_txt = COLORS["green"], f"{len(rdv_list)} RDV"
            else:
                badge_bg, badge_txt = "#94a3b8", "Libre"

            badge = QLabel(f"  {badge_txt}  ")
            badge.setStyleSheet(f"""
                background-color: {badge_bg};
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 6px;
                padding: 3px 6px;
            """)
            day_hdr.addWidget(badge)
            card_l.addLayout(day_hdr)

            for rdv in rdv_list:
                start_h = format_time(rdv.get("start", ""))
                summary = rdv.get("summary", "")
                loc     = rdv.get("location", "")
                name_s  = summary.split("|")[1].strip() if "|" in summary else summary.strip()

                rdv_frame = QFrame()
                rdv_frame.setStyleSheet(f"background-color: {COLORS['surface2']}; border: none; border-radius: 6px;")
                rdv_l = QVBoxLayout(rdv_frame)
                rdv_l.setContentsMargins(10, 8, 10, 8)
                rdv_l.setSpacing(4)

                top_row = QHBoxLayout()
                top_row.setSpacing(8)

                if start_h:
                    time_lbl = QLabel(f" {start_h} ")
                    time_lbl.setStyleSheet(f"""
                        background-color: {COLORS['accent']};
                        color: white;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 2px 6px;
                    """)
                    time_lbl.setFixedHeight(24)
                    top_row.addWidget(time_lbl)

                name_lbl = QLabel(name_s)
                name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: bold; background: transparent;")
                name_lbl.setWordWrap(True)
                top_row.addWidget(name_lbl)
                top_row.addStretch()
                rdv_l.addLayout(top_row)

                if loc:
                    addr_short = ", ".join(loc.split(",")[:2])[:50]
                    addr_lbl = QLabel(f"📍 {addr_short}")
                    addr_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
                    addr_lbl.setWordWrap(True)
                    rdv_l.addWidget(addr_lbl)

                card_l.addWidget(rdv_frame)

            card.mousePressEvent = lambda e, dk=date_key: self._on_click(dk)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            content_l.addWidget(card)

        content_l.addStretch()
        scroll.setWidget(content)
        self.content_layout.addWidget(scroll)

    def _on_click(self, date_key):
        self.selected = date_key
        self._render()
        if self.on_day_click:
            self.on_day_click(date_key, self.month_events.get(date_key, []))

    def get_month_events(self):
        return self.month_events