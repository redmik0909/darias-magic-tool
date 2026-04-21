import threading
import webbrowser
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QSplitter, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer

from config import COLORS, ZONE_COLORS, PRIORITY_COLORS, MOIS_FR, JOURS_FR, styled_btn
from utils import geocode_address, find_zone, geocode_coords, osrm_route
from google_cal import format_time
from pages.cal_widget import (
    GoogleCalWidget, find_cal_id, is_real_rdv,
    is_blocked_day, get_avoided_slots, show_day_popup
)

CRENEAUX = [
    ("9h00",  "9h00 – 10h00"),
    ("11h00", "11h00 – 12h00"),
    ("13h00", "13h00 – 14h00"),
    ("15h00", "15h00 – 16h00"),
    ("17h00", "17h00 – 18h00"),
]


class WorkerSignals(QObject):
    result  = pyqtSignal(object, str)
    error   = pyqtSignal(str)
    hors    = pyqtSignal(str)


class SearchWorker(threading.Thread):
    def __init__(self, address, data, signals):
        super().__init__(daemon=True)
        self.address = address
        self.data    = data
        self.signals = signals

    def run(self):
        city, full_address = geocode_address(self.address)
        if not city:
            self.signals.error.emit("Adresse introuvable")
            return
        coords = geocode_coords(full_address or self.address)
        zone, _ = find_zone(city, self.data)
        if zone == "hors_territoire":
            self.signals.hors.emit(city)
        elif zone is None:
            self.signals.error.emit(f"Zone non configurée pour : {city}")
        else:
            self.signals.result.emit((zone, coords), city)


class SuggestWorker(threading.Thread):
    def __init__(self, rep, month_events, client_coords, signals):
        super().__init__(daemon=True)
        self.rep          = rep
        self.month_events = month_events
        self.client_coords = client_coords
        self.signals      = signals

    def run(self):
        today   = datetime.today()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        scored  = []

        for date_key, events in self.month_events.items():
            try:
                day_dt = datetime.strptime(date_key, "%Y-%m-%d")
            except Exception:
                continue
            if day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0):
                continue
            if is_blocked_day(events):
                continue

            real_rdv = [e for e in events if is_real_rdv(e)]
            if len(real_rdv) >= max_rdv:
                continue

            taken_hrs   = {format_time(e["start"])[:2] for e in real_rdv if format_time(e["start"])}
            avoided_hrs = get_avoided_slots(events)
            free_slots  = [(k, v) for k, v in CRENEAUX
                          if k[:2] not in taken_hrs and k[:2] not in avoided_hrs]
            if not free_slots:
                continue

            min_dist, closest_rdv = None, None
            for rdv in real_rdv[:3]:
                loc = rdv.get("location", "")
                if not loc:
                    continue
                try:
                    coords = geocode_coords(loc)
                    if not coords:
                        continue
                    result = osrm_route([self.client_coords, (coords[0], coords[1])])
                    if result and result[0]:
                        dist = result[0][0][1]
                        if min_dist is None or dist < min_dist:
                            min_dist, closest_rdv = dist, rdv
                except Exception:
                    continue

            score = (min_dist or 999999) + (len(real_rdv) * 1000)
            scored.append({
                "date_key": date_key, "day_dt": day_dt,
                "slot": free_slots[0][1], "dist_sec": min_dist,
                "closest_rdv": closest_rdv, "nb_rdv": len(real_rdv), "score": score,
            })

        scored.sort(key=lambda x: x["score"])
        self.signals.result.emit(scored[:3], "")


class RecherchePage(QWidget):
    cal_ready = pyqtSignal(str)

    def __init__(self, data):
        super().__init__()
        self.data           = data
        self.rep            = None
        self.cal_widget     = None
        self.client_address = ""
        self.client_coords  = None
        self.zone_reps      = []
        self.prio_index     = 0
        self.suggest_widget = None
        self.suggest_btn    = None
        self.setStyleSheet(f"background-color: {COLORS['bg']};")
        self.cal_ready.connect(self._on_cal_ready)
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
        title = QLabel("Recherche de territoire")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 16px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(title)
        hdr_l.addStretch()
        layout.addWidget(hdr)

        # Splitter — left panel / right panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; width: 12px; }")

        # ── Left panel ────────────────────────────────────────────────────────
        left_container = QFrame()
        left_container.setStyleSheet(f"""
            QFrame#leftPanel {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        left_container.setObjectName("leftPanel")
        self.left_layout = QVBoxLayout(left_container)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        # Search card
        search_card = QFrame()
        search_card.setObjectName("searchCard")
        search_card.setStyleSheet(f"""
            QFrame#searchCard {{
                background-color: {COLORS['surface2']};
                border-radius: 8px;
                border: none;
                margin: 14px 14px 10px 14px;
            }}
            QFrame#searchCard QLabel {{ border: none; background: transparent; }}
        """)
        search_l = QVBoxLayout(search_card)
        search_l.setContentsMargins(12, 10, 12, 10)
        search_l.setSpacing(8)

        addr_lbl = QLabel("Adresse du client")
        addr_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent;")
        search_l.addWidget(addr_lbl)

        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Adresse ou code postal...")
        self.entry.setFixedHeight(40)
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                background: white;
                color: {COLORS['text']};
                selection-background-color: {COLORS['accent']};
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)
        self.entry.returnPressed.connect(self._search)
        entry_row.addWidget(self.entry)

        self.search_btn = styled_btn("Rechercher", COLORS["accent"], height=40, width=120)
        self.search_btn.clicked.connect(self._search)
        entry_row.addWidget(self.search_btn)
        search_l.addLayout(entry_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        search_l.addWidget(self.status_lbl)

        self.left_layout.addWidget(search_card)

        # Scrollable rep area
        self.rep_scroll = QScrollArea()
        self.rep_scroll.setWidgetResizable(True)
        self.rep_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.rep_content = QWidget()
        self.rep_content.setStyleSheet("background: transparent;")
        self.rep_content_l = QVBoxLayout(self.rep_content)
        self.rep_content_l.setContentsMargins(8, 0, 8, 8)
        self.rep_content_l.setSpacing(6)

        placeholder = QLabel("Entrez une adresse pour voir\nle représentant et son calendrier")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px; background: transparent;")
        self.rep_content_l.addWidget(placeholder, alignment=Qt.AlignmentFlag.AlignCenter)
        self.rep_content_l.addStretch()

        self.rep_scroll.setWidget(self.rep_content)
        self.left_layout.addWidget(self.rep_scroll)

        splitter.addWidget(left_container)

        # ── Right panel ───────────────────────────────────────────────────────
        self.right_container = QFrame()
        self.right_container.setObjectName("rightPanel")
        self.right_container.setStyleSheet(f"""
            QFrame#rightPanel {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        placeholder_r = QLabel("Le calendrier s'affichera ici")
        placeholder_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_r.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 13px; background: transparent;")
        self.right_layout.addWidget(placeholder_r)

        splitter.addWidget(self.right_container)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter, stretch=1)

    def refresh(self):
        if self.cal_widget and self.cal_widget.cal_id:
            self.cal_widget.load(self.cal_widget.cal_id)

    def _clear_rep(self):
        while self.rep_content_l.count():
            item = self.rep_content_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_right(self):
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cal_widget = None

    # ── Search ────────────────────────────────────────────────────────────────
    def _search(self):
        address = self.entry.text().strip()
        if not address:
            return
        self.client_address = address
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Recherche...")
        self.status_lbl.setText("Géolocalisation en cours...")
        self._clear_rep()

        self.search_signals = WorkerSignals()
        self.search_signals.result.connect(self._on_search_result)
        self.search_signals.error.connect(self._err)
        self.search_signals.hors.connect(self._hors_territoire)

        SearchWorker(address, self.data, self.search_signals).start()

    def _on_search_result(self, payload, city):
        zone, coords = payload
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Rechercher")
        self.status_lbl.setText(f"Ville détectée : {city}")

        if coords:
            self.client_coords = (coords[0], coords[1])

        p1_rep = next((r for r in zone["representants"] if r["priorite"] == 1), None)
        if not p1_rep:
            lbl = QLabel("Aucun représentant Priorité 1.")
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent;")
            self.rep_content_l.addWidget(lbl)
            return

        self.rep        = p1_rep
        self.zone_reps  = sorted(zone["representants"], key=lambda r: r["priorite"])
        self.prio_index = 0
        self._show_rep_info(zone)
        self._load_calendar()

    def _load_calendar(self):
        self._clear_right()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        self.cal_widget = GoogleCalWidget(None, self.rep,
                                          on_day_click=self._on_day_click,
                                          max_rdv=max_rdv)
        self.right_layout.addWidget(self.cal_widget)

        # Suggest button at bottom of left
        self._make_suggest_btn()

        threading.Thread(target=self._fetch_cal, daemon=True).start()

    def _on_cal_ready(self, cal_id):
        if cal_id and self.cal_widget:
            self.cal_widget.load(cal_id)
        elif not cal_id:
            self.status_lbl.setText("Calendrier Google non trouvé")

    def _fetch_cal(self):
        cal_id = find_cal_id(self.rep)
        if cal_id:
            self.cal_ready.emit(cal_id)
        else:
            self.cal_ready.emit("")

    def _make_suggest_btn(self):
        # Remove old suggest btn and widget
        if self.suggest_btn:
            self.suggest_btn.deleteLater()
            self.suggest_btn = None
        if self.suggest_widget:
            self.suggest_widget.deleteLater()
            self.suggest_widget = None

        self.suggest_btn = styled_btn("💡 Calculer les suggestions", COLORS["green"], height=36)
        self.suggest_btn.clicked.connect(self._start_suggestions)
        self.left_layout.addWidget(self.suggest_btn)
        self.left_layout.setContentsMargins(0, 0, 0, 8)

    # ── Rep info ──────────────────────────────────────────────────────────────
    def _show_rep_info(self, zone):
        self._clear_rep()
        zone_color = ZONE_COLORS.get(zone["id"], COLORS["accent"])

        # Zone banner
        banner = QFrame()
        banner.setFixedHeight(36)
        banner.setStyleSheet(f"background-color: {zone_color}; border-radius: 8px;")
        banner_l = QHBoxLayout(banner)
        banner_l.setContentsMargins(12, 0, 12, 0)
        banner_lbl = QLabel(f"  {zone['nom'].upper()}")
        banner_lbl.setStyleSheet("color: white; font-size: 13px; font-weight: bold; background: transparent;")
        banner_l.addWidget(banner_lbl)
        self.rep_content_l.addWidget(banner)

        # Nav row
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)

        map_btn = styled_btn("🗺 Voir sur la carte", COLORS["purple"], height=32, width=180)
        map_btn.clicked.connect(self._open_map)
        nav_row.addWidget(map_btn)
        nav_row.addStretch()

        if len(self.zone_reps) > 1:
            prev_idx = self.prio_index - 1
            next_idx = self.prio_index + 1
            if prev_idx >= 0:
                prev_btn = styled_btn("←", COLORS["accent"], height=32, width=40)
                prev_btn.clicked.connect(lambda _, i=prev_idx: self._switch_prio(i))
                nav_row.addWidget(prev_btn)
            if next_idx < len(self.zone_reps):
                next_btn = styled_btn("→", COLORS["accent"], height=32, width=40)
                next_btn.clicked.connect(lambda _, i=next_idx: self._switch_prio(i))
                nav_row.addWidget(next_btn)

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: transparent;")
        nav_widget.setLayout(nav_row)
        self.rep_content_l.addWidget(nav_widget)

        # Rep card
        rep = self.rep
        card = QFrame()
        card.setObjectName("repCard")
        card.setStyleSheet(f"""
            QFrame#repCard {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame#repCard QLabel {{ border: none; background: transparent; }}
        """)
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(12, 10, 12, 10)
        card_l.setSpacing(6)

        # Priority badge + name
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        prio       = rep.get("priorite", 99)
        prio_color = PRIORITY_COLORS.get(prio, "#64748b")
        prio_label = f"PRIORITÉ {prio}" if prio <= 3 else "AUTRE"

        badge = QLabel(f"  {prio_label}  ")
        badge.setStyleSheet(f"""
            background-color: {prio_color};
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 4px;
        """)
        badge.setFixedHeight(22)
        top_row.addWidget(badge)

        name_lbl = QLabel(rep["nom"])
        name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 15px; font-weight: bold; background: transparent;")
        top_row.addWidget(name_lbl)
        top_row.addStretch()
        card_l.addLayout(top_row)

        cal_lbl = QLabel(f"  {rep.get('calendrier', '')}")
        cal_lbl.setStyleSheet(f"color: {COLORS['accent']}; font-size: 11px; background: transparent;")
        card_l.addWidget(cal_lbl)

        jour_lbl = QLabel(f"  {rep.get('jours', '')}")
        jour_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        card_l.addWidget(jour_lbl)

        if rep.get("rdv_par_jour"):
            rdv_lbl = QLabel(f"  Max {rep['rdv_par_jour']} RDV/jour")
            rdv_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
            card_l.addWidget(rdv_lbl)

        if rep.get("regles"):
            rules_frame = QFrame()
            rules_frame.setStyleSheet(f"background-color: {COLORS['bg']}; border-radius: 6px; border: none;")
            rules_l = QVBoxLayout(rules_frame)
            rules_l.setContentsMargins(8, 4, 8, 4)
            for r in rep["regles"]:
                r_lbl = QLabel(f"  {r}")
                r_lbl.setWordWrap(True)
                r_lbl.setStyleSheet(f"color: {COLORS['orange']}; font-size: 10px; background: transparent;")
                rules_l.addWidget(r_lbl)
            card_l.addWidget(rules_frame)

        self.rep_content_l.addWidget(card)

        # Address card
        addr_card = QFrame()
        addr_card.setObjectName("addrCard")
        addr_card.setStyleSheet(f"""
            QFrame#addrCard {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame#addrCard QLabel {{ border: none; background: transparent; }}
        """)
        addr_l = QVBoxLayout(addr_card)
        addr_l.setContentsMargins(12, 10, 12, 10)
        addr_l.setSpacing(4)

        addr_title = QLabel("📍  Adresse à booker")
        addr_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: bold; background: transparent;")
        addr_l.addWidget(addr_title)

        addr_val = QLabel(self.client_address)
        addr_val.setWordWrap(True)
        addr_val.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: bold; background: transparent;")
        addr_l.addWidget(addr_val)

        self.rep_content_l.addWidget(addr_card)
        self.rep_content_l.addStretch()

    # ── Switch priority ────────────────────────────────────────────────────────
    def _switch_prio(self, idx):
        if idx < 0 or idx >= len(self.zone_reps):
            return
        self.prio_index = idx
        self.rep        = self.zone_reps[idx]

        zone = None
        for z in self.data["zones"]:
            if any(r["nom"] == self.rep["nom"] for r in z["representants"]):
                zone = z
                break
        if not zone:
            return

        self._show_rep_info(zone)
        self._load_calendar()

    # ── Map ────────────────────────────────────────────────────────────────────
    def _open_map(self):
        if self.client_coords:
            lat, lon = self.client_coords
            webbrowser.open(f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16")
        else:
            webbrowser.open(f"https://www.openstreetmap.org/search?query={self.client_address.replace(' ', '+')}")

    # ── Day click ─────────────────────────────────────────────────────────────
    def _on_day_click(self, date_key, events):
        show_day_popup(self, self.rep, date_key, events)

    # ── Suggestions ───────────────────────────────────────────────────────────
    def _start_suggestions(self):
        if not self.client_coords:
            self.status_lbl.setText("Coordonnées client introuvables.")
            return
        self.suggest_btn.setEnabled(False)
        self.suggest_btn.setText("Calcul en cours...")

        # Loading widget
        if self.suggest_widget:
            self.suggest_widget.deleteLater()
        self.suggest_widget = QFrame()
        self.suggest_widget.setObjectName("loadingWidget")
        self.suggest_widget.setStyleSheet(f"""
            QFrame#loadingWidget {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame#loadingWidget QLabel {{ border: none; background: transparent; }}
        """)
        loading_l = QVBoxLayout(self.suggest_widget)
        loading_lbl = QLabel("⏳  Calcul des meilleures dates...")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent;")
        loading_l.addWidget(loading_lbl)
        self.left_layout.insertWidget(self.left_layout.count() - 1, self.suggest_widget)

        self.suggest_signals = WorkerSignals()
        self.suggest_signals.result.connect(self._show_suggestions)

        SuggestWorker(
            self.rep,
            self.cal_widget.get_month_events() if self.cal_widget else {},
            self.client_coords,
            self.suggest_signals
        ).start()

    def _show_suggestions(self, suggestions, _):
        self.suggest_btn.setEnabled(True)
        self.suggest_btn.setText("🔄 Recalculer les suggestions")

        if self.suggest_widget:
            self.suggest_widget.deleteLater()

        self.suggest_widget = QFrame()
        self.suggest_widget.setObjectName("suggestWidget")
        self.suggest_widget.setStyleSheet(f"""
            QFrame#suggestWidget {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame#suggestWidget QLabel {{ border: none; background: transparent; }}
            QFrame#suggestWidget QFrame {{ border: none; }}
        """)
        sw_l = QVBoxLayout(self.suggest_widget)
        sw_l.setContentsMargins(0, 0, 0, 8)
        sw_l.setSpacing(4)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {COLORS['sidebar']}; border-radius: 8px 8px 0 0;")
        hdr.setFixedHeight(40)
        hdr_l = QHBoxLayout(hdr)
        hdr_lbl = QLabel("  💡  Meilleures disponibilités")
        hdr_lbl.setStyleSheet("color: white; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(hdr_lbl)
        sw_l.addWidget(hdr)

        if not suggestions:
            no_lbl = QLabel("Aucune disponibilité trouvée ce mois-ci.")
            no_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent; padding: 12px;")
            sw_l.addWidget(no_lbl)
        else:
            rank_colors = ["#16a34a", "#2563eb", "#d97706"]
            medals      = ["#1", "#2", "#3"]

            for i, s in enumerate(suggestions):
                day_parts = s["date_key"].split("-")
                day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]}"
                sun_wd    = (s["day_dt"].weekday() + 1) % 7
                weekday   = JOURS_FR[sun_wd]

                card = QFrame()
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {COLORS['surface']};
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        margin: 0 8px;
                    }}
                """)
                card_l = QVBoxLayout(card)
                card_l.setContentsMargins(10, 8, 10, 8)
                card_l.setSpacing(4)

                top_row = QHBoxLayout()
                medal_lbl = QLabel(f" {medals[i]} ")
                medal_lbl.setStyleSheet(f"""
                    background-color: {rank_colors[i]};
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 2px 6px;
                """)
                medal_lbl.setFixedHeight(22)
                top_row.addWidget(medal_lbl)

                slot_lbl = QLabel(f"{weekday} {day_fmt}  —  {s['slot']}")
                slot_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: bold; background: transparent;")
                top_row.addWidget(slot_lbl)
                top_row.addStretch()

                copy_btn = styled_btn("📋 Copier", COLORS["accent"], height=28, width=90)
                copy_btn.clicked.connect(lambda _, sv=s, wv=weekday, df=day_fmt: self._copy(sv, wv, df))
                top_row.addWidget(copy_btn)
                card_l.addLayout(top_row)

                if s["dist_sec"] is not None:
                    dist_min = int(s["dist_sec"] // 60)
                    rdv_name = s["closest_rdv"].get("summary", "")[:35] if s["closest_rdv"] else ""
                    det_lbl  = QLabel(f"📍 À {dist_min} min d'un RDV existant  •  {s['nb_rdv']} RDV ce jour")
                    det_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; background: transparent;")
                    card_l.addWidget(det_lbl)
                    if rdv_name:
                        rdv_lbl = QLabel(f"   ↳ {rdv_name}")
                        rdv_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; background: transparent;")
                        card_l.addWidget(rdv_lbl)
                else:
                    free_lbl = QLabel(f"📅 Journée libre  •  {s['nb_rdv']} RDV ce jour")
                    free_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; background: transparent;")
                    card_l.addWidget(free_lbl)

                sw_l.addWidget(card)

        self.left_layout.insertWidget(self.left_layout.count() - 1, self.suggest_widget)

    def _copy(self, s, weekday, day_fmt):
        day_parts = s["date_key"].split("-")
        full_fmt  = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]} {day_parts[0]}"
        text = f"{self.rep['nom']} - {s['slot']} - {weekday} {full_fmt} - {self.client_address}"
        QApplication.clipboard().setText(text)
        self.status_lbl.setText(f"📋 Copié : {s['slot']} le {weekday} {day_fmt}")

    # ── Errors ────────────────────────────────────────────────────────────────
    def _hors_territoire(self, city):
        self._clear_rep()
        self._clear_right()
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Rechercher")
        self.status_lbl.setText(f"Ville : {city}")

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface2']};
                border: 1px solid {COLORS['red']};
                border-radius: 8px;
            }}
        """)
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(16, 16, 16, 16)
        card_l.setSpacing(8)

        title = QLabel("HORS TERRITOIRE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLORS['red']}; font-size: 16px; font-weight: bold; background: transparent;")
        card_l.addWidget(title)

        msg = QLabel(f"La ville {city} n'est pas desservie.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent;")
        card_l.addWidget(msg)

        self.rep_content_l.addWidget(card)
        self.rep_content_l.addStretch()

    def _err(self, message):
        self._clear_rep()
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Rechercher")
        self.status_lbl.setText("")

        err_lbl = QLabel(message)
        err_lbl.setStyleSheet(f"color: {COLORS['orange']}; font-size: 12px; background: transparent;")
        self.rep_content_l.addWidget(err_lbl)
        self.rep_content_l.addStretch()