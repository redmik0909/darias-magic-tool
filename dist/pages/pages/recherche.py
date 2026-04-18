import customtkinter as ctk
import threading
import calendar
import webbrowser
from datetime import datetime
from config import C, ZONE_COLORS, label, btn
from utils import geocode_address, find_zone, geocode_coords, osrm_route
from google_cal import get_events_for_month, find_calendar_by_name, format_time

MOIS_FR   = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR  = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]  # Commence dimanche
CRENEAUX  = [
    ("9h00",  "9h00 – 10h00"),
    ("11h00", "11h00 – 12h00"),
    ("13h00", "13h00 – 14h00"),
    ("15h00", "15h00 – 16h00"),
    ("17h00", "17h00 – 18h00"),
]
SKIP_KEYWORDS = ["PAS DE RDV", "INDISPONIBLE", "CONGE", "CONGÉ", "FÉRIÉ", "FERIE"]


def _is_real_rdv(e):
    return not any(x in e.get("summary", "").upper() for x in SKIP_KEYWORDS)


class RecherchePage(ctk.CTkFrame):
    def __init__(self, parent, data):
        super().__init__(parent, fg_color=C["bg"])
        self.data           = data
        self.rep            = None
        self.cal_id         = None
        self.cal_date       = datetime.today().replace(day=1)
        self.client_address = ""
        self.client_coords  = None
        self.month_events   = {}
        self.selected_date  = None
        self.suggest_frame  = None
        self.view_mode      = "calendar"  # "calendar" or "list"
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        ph = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        ph.pack(fill="x")
        label(ph, "Recherche de territoire", size=16, weight="bold").pack(side="left", padx=20, pady=14)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Left panel
        self.left = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                                  border_width=1, border_color=C["border"])
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        search_card = ctk.CTkFrame(self.left, fg_color=C["surface2"], corner_radius=8)
        search_card.pack(fill="x", padx=14, pady=(14, 10))
        label(search_card, "Adresse du client", size=12,
              color=C["text_muted"]).pack(anchor="w", padx=12, pady=(10, 4))

        row = ctk.CTkFrame(search_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))

        self.entry = ctk.CTkEntry(row, placeholder_text="Adresse ou code postal...",
            height=40, font=ctk.CTkFont(size=13), corner_radius=6,
            fg_color=C["surface"], border_color=C["border"])
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._search())

        self.search_btn = btn(row, "Rechercher", self._search, width=120, height=40)
        self.search_btn.pack(side="left")

        self.status_var = ctk.StringVar(value="")
        ctk.CTkLabel(search_card, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11),
                     text_color=C["text_muted"]).pack(anchor="w", padx=12, pady=(0, 6))

        self.rep_frame = ctk.CTkScrollableFrame(self.left, fg_color="transparent")
        self.rep_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        label(self.rep_frame,
              "Entrez une adresse pour voir\nle représentant et son calendrier",
              size=12, color=C["text_dim"], justify="center").pack(pady=40)

        # Right panel
        self.right = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                                   border_width=1, border_color=C["border"])
        self.right.grid(row=0, column=1, sticky="nsew")
        label(self.right, "Le calendrier s'affichera ici",
              size=13, color=C["text_dim"]).pack(expand=True)

    def refresh(self):
        if self.rep and self.cal_id:
            self._load_calendar()

    def _clear_rep(self):
        for w in self.rep_frame.winfo_children():
            w.destroy()

    def _clear_cal(self):
        for w in self.right.winfo_children():
            w.destroy()

    # ── Search ────────────────────────────────────────────────────────────────
    def _search(self):
        address = self.entry.get().strip()
        if not address:
            return
        self.client_address = address
        self.search_btn.configure(state="disabled", text="Recherche...")
        self.status_var.set("Géolocalisation en cours...")
        self._clear_rep()
        threading.Thread(target=self._worker, args=(address,), daemon=True).start()

    def _worker(self, address):
        city, full_address = geocode_address(address)
        if not city:
            self.after(0, self._err, "Adresse introuvable")
            return
        coords = geocode_coords(address)
        if coords:
            self.client_coords = (coords[0], coords[1])
        zone, _ = find_zone(city, self.data)
        if zone == "hors_territoire":
            self.after(0, self._hors_territoire, city)
        elif zone is None:
            self.after(0, self._err, f"Zone non configurée pour : {city}")
        else:
            self.after(0, self._show, zone, city, full_address)

    def _show(self, zone, city, full_address):
        self._clear_rep()
        self._clear_cal()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set(f"Ville détectée : {city}")

        p1_rep = next((r for r in zone["representants"] if r["priorite"] == 1), None)
        if not p1_rep:
            label(self.rep_frame, "Aucun représentant Priorité 1.",
                  size=12, color=C["text_muted"]).pack(pady=20)
            return

        self.rep = p1_rep
        threading.Thread(target=self._find_and_load_cal,
                        args=(zone, full_address), daemon=True).start()

    def _find_and_load_cal(self, zone, full_address):
        try:
            rep_nom  = self.rep["nom"]
            keywords = [rep_nom.split()[0]]
            if len(rep_nom.split()) > 1:
                keywords.append(rep_nom.split()[1])
            cal_field = self.rep.get("google_calendar", "")
            if cal_field:
                for p in [x.strip() for x in cal_field.replace("/", ",").split(",")]:
                    if p and p.upper() not in ["RDV", "MTL", "TR"]:
                        keywords.append(p[:10])

            cal_id = None
            for kw in keywords:
                cal_id, _ = find_calendar_by_name(kw)
                if cal_id:
                    break

            self.cal_id = cal_id
            self.after(0, self._show_rep_info, zone)
            if cal_id:
                self._load_calendar_data()
        except Exception:
            self.cal_id = None
            self.after(0, self._show_rep_info, zone)

    # ── Rep info ──────────────────────────────────────────────────────────────
    def _show_rep_info(self, zone):
        self._clear_rep()
        zone_color = ZONE_COLORS.get(zone["id"], C["accent"])

        banner = ctk.CTkFrame(self.rep_frame, fg_color=zone_color, corner_radius=8)
        banner.pack(fill="x", pady=(4, 8))
        label(banner, f"  {zone['nom'].upper()}", size=13, weight="bold",
              color="#ffffff").pack(side="left", padx=12, pady=8)

        btn(self.rep_frame, "🗺  Voir sur la carte",
            lambda: webbrowser.open(
                f"https://www.openstreetmap.org/search?query={self.client_address.replace(' ', '+')}"),
            width=200, height=32, color=C["purple"], hover="#6e40c9").pack(anchor="w", pady=(0, 8))

        rep  = self.rep
        card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                            border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=(0, 8))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top, text="  PRIORITÉ 1  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     fg_color=C["p1"], text_color="white",
                     corner_radius=4).pack(side="left", padx=(0, 10))
        label(top, rep["nom"], size=15, weight="bold").pack(side="left")

        det = ctk.CTkFrame(card, fg_color="transparent")
        det.pack(fill="x", padx=12, pady=(0, 6))
        label(det, f"📅  {rep['calendrier']}", size=11, color=C["accent"], anchor="w").pack(fill="x", pady=1)
        label(det, f"🗓️  {rep['jours']}", size=11, color=C["text_muted"], anchor="w").pack(fill="x", pady=1)
        if rep.get("rdv_par_jour"):
            label(det, f"📊  Max {rep['rdv_par_jour']} RDV/jour", size=11,
                  color=C["text_muted"], anchor="w").pack(fill="x", pady=1)

        if rep.get("regles"):
            rb = ctk.CTkFrame(card, fg_color=C["bg"], corner_radius=6)
            rb.pack(fill="x", padx=12, pady=(4, 10))
            for r in rep["regles"]:
                label(rb, f"  {r}", size=10, color=C["orange"],
                      anchor="w", wraplength=300).pack(fill="x", padx=8, pady=1)
        else:
            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

        addr_card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                                  border_width=1, border_color=C["border"])
        addr_card.pack(fill="x", pady=(0, 8))
        label(addr_card, "📍  Adresse à booker", size=12, weight="bold",
              color=C["text_muted"]).pack(anchor="w", padx=12, pady=(10, 4))
        label(addr_card, self.client_address, size=12, weight="bold",
              color=C["text"]).pack(anchor="w", padx=12, pady=(0, 10))

        if not self.cal_id:
            label(self.rep_frame, "⚠  Calendrier Google non trouvé",
                  size=11, color=C["orange"]).pack(anchor="w", padx=4)

    # ── Calendar loading ──────────────────────────────────────────────────────
    def _load_calendar_data(self):
        try:
            y, m = self.cal_date.year, self.cal_date.month
            self.month_events = get_events_for_month(self.cal_id, y, m)
            self.after(0, self._render_calendar)
            if self.client_coords:
                self.after(500, self._show_suggestions_loading)
                threading.Thread(target=self._compute_monthly_suggestions, daemon=True).start()
        except Exception:
            self.after(0, self._render_calendar)

    def _load_calendar(self):
        if self.cal_id:
            threading.Thread(target=self._load_calendar_data, daemon=True).start()

    # ── Calendar render — Vue liste ───────────────────────────────────────────
    def _render_calendar(self):
        self._clear_cal()
        if not self.rep:
            return

        y, m    = self.cal_date.year, self.cal_date.month
        today   = datetime.today()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        _, days_in_month = calendar.monthrange(y, m)

        # Header
        cal_hdr = ctk.CTkFrame(self.right, fg_color=C["surface"], corner_radius=0)
        cal_hdr.pack(fill="x")
        label(cal_hdr, f"Calendrier — {self.rep['nom']}",
              size=13, weight="bold").pack(side="left", padx=16, pady=12)

        nav = ctk.CTkFrame(cal_hdr, fg_color="transparent")
        nav.pack(side="right", padx=12)
        btn(nav, "<", self._prev_month, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)
        label(nav, f"{MOIS_FR[m]} {y}", size=12, weight="bold",
              color=C["text"]).pack(side="left", padx=8)
        btn(nav, ">", self._next_month, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)

        # View toggle
        toggle = ctk.CTkFrame(self.right, fg_color=C["surface2"], corner_radius=0)
        toggle.pack(fill="x", padx=8, pady=(4, 0))

        ctk.CTkButton(toggle, text="📅  Calendrier",
                      width=130, height=30, corner_radius=6,
                      fg_color=C["accent"] if self.view_mode == "calendar" else C["surface"],
                      hover_color=C["accent_h"],
                      text_color="white" if self.view_mode == "calendar" else C["text_muted"],
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._switch_to_calendar
                      ).pack(side="left", padx=6, pady=6)

        ctk.CTkButton(toggle, text="☰  Liste",
                      width=100, height=30, corner_radius=6,
                      fg_color=C["accent"] if self.view_mode == "list" else C["surface"],
                      hover_color=C["accent_h"],
                      text_color="white" if self.view_mode == "list" else C["text_muted"],
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._switch_to_list
                      ).pack(side="left", padx=2, pady=6)

        # Content area — grid or list
        if self.view_mode == "list":
            # List view — scrollable day cards
            scroll = ctk.CTkScrollableFrame(self.right, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=10, pady=8)
        else:
            # Calendar grid view
            self._render_calendar_grid(self.right)
            return

        for day in range(1, days_in_month + 1):
            date_key = f"{y}-{m:02d}-{day:02d}"
            day_dt   = datetime(y, m, day)
            # weekday: Python 0=Mon,6=Sun → convert to Sun=0
            py_wd    = day_dt.weekday()
            sunday_first_wd = (py_wd + 1) % 7  # 0=Sun,1=Mon,...,6=Sat
            is_today = (today.year == y and today.month == m and today.day == day)
            is_past  = day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0)
            is_off   = sunday_first_wd == 0 or sunday_first_wd == 6  # Sun or Sat

            if is_past or is_off:
                continue

            rdv_list = [e for e in self.month_events.get(date_key, []) if _is_real_rdv(e)]
            is_full  = len(rdv_list) >= max_rdv
            is_sel   = self.selected_date == date_key

            # Day card color
            if is_sel:
                bg, border_col, border_w = "#dbeafe", C["accent"], 2
            elif is_today:
                bg, border_col, border_w = "#f0f9ff", C["accent"], 2
            elif is_full:
                bg, border_col, border_w = "#fef2f2", C["red"], 1
            else:
                bg, border_col, border_w = C["surface"], C["border"], 1

            day_card = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=10,
                                    border_width=border_w, border_color=border_col)
            day_card.pack(fill="x", pady=4)

            # Day header
            day_hdr = ctk.CTkFrame(day_card, fg_color="transparent")
            day_hdr.pack(fill="x", padx=14, pady=(10, 6))

            jour_nom = JOURS_FR[sunday_first_wd]
            ctk.CTkLabel(day_hdr,
                         text=f"{jour_nom}  {day} {MOIS_FR[m]}",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=C["accent"] if (is_today or is_sel) else C["text"]
                         ).pack(side="left")

            # Badge
            if is_full:
                badge_fg, badge_txt = C["red"], f"Complet · {len(rdv_list)} RDV"
            elif rdv_list:
                badge_fg, badge_txt = C["green"], f"{len(rdv_list)} RDV"
            else:
                badge_fg, badge_txt = "#94a3b8", "Libre"

            ctk.CTkLabel(day_hdr, text=f"  {badge_txt}  ",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         fg_color=badge_fg, text_color="white",
                         corner_radius=6).pack(side="right")

            # RDV rows — list view
            for rdv in rdv_list:
                start_h  = format_time(rdv.get("start", ""))
                summary  = rdv.get("summary", "")
                location = rdv.get("location", "")
                name_s   = summary.split("|")[1].strip() if "|" in summary else summary.strip()

                rdv_row = ctk.CTkFrame(day_card, fg_color=C["surface2"], corner_radius=6)
                rdv_row.pack(fill="x", padx=10, pady=2)
                inner = ctk.CTkFrame(rdv_row, fg_color="transparent")
                inner.pack(fill="x", padx=10, pady=8)
                top_row = ctk.CTkFrame(inner, fg_color="transparent")
                top_row.pack(fill="x")

                if start_h:
                    ctk.CTkLabel(top_row, text=f" {start_h} ",
                                 font=ctk.CTkFont(size=11, weight="bold"),
                                 fg_color=C["accent"], text_color="white",
                                 corner_radius=4).pack(side="left", padx=(0, 10))

                ctk.CTkLabel(top_row, text=name_s,
                             font=ctk.CTkFont(size=13, weight="bold"),
                             text_color=C["text"], anchor="w").pack(side="left")

                if location:
                    addr_short = ", ".join(location.split(",")[:2])[:50]
                    ctk.CTkLabel(inner, text=f"📍 {addr_short}",
                                 font=ctk.CTkFont(size=11),
                                 text_color=C["text_muted"],
                                 anchor="w").pack(anchor="w", pady=(4, 0))

            ctk.CTkFrame(day_card, fg_color="transparent", height=6).pack()

            def make_click(dk):
                return lambda e: self._select_day(dk)

            day_card.bind("<Button-1>", make_click(date_key))
            for w in day_card.winfo_children():
                w.bind("<Button-1>", make_click(date_key))
                for ww in w.winfo_children():
                    ww.bind("<Button-1>", make_click(date_key))

    def _switch_to_calendar(self):
        self.view_mode = "calendar"
        self._render_calendar()

    def _switch_to_list(self):
        self.view_mode = "list"
        self._render_calendar()

    def _render_list_view(self):
        """Already rendered by _render_calendar when view_mode == list."""
        pass

    def _render_calendar_grid(self, parent):
        """Render the monthly grid view."""
        y, m    = self.cal_date.year, self.cal_date.month
        today   = datetime.today()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        _, days_in_month = calendar.monthrange(y, m)

        # Day headers — Sun first
        JOURS_GRID = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
        hdr = ctk.CTkFrame(parent, fg_color=C["surface2"], corner_radius=0)
        hdr.pack(fill="x", padx=4)
        hdr.columnconfigure(list(range(7)), weight=1)
        for i, j in enumerate(JOURS_GRID):
            label(hdr, j, size=11, weight="bold",
                  color=C["text_muted"]).grid(row=0, column=i, padx=2, pady=6, sticky="nsew")

        # Scrollable grid
        grid_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        grid_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        grid_scroll.columnconfigure(list(range(7)), weight=1)

        # First day column — Python weekday to Sun-first
        first_py_wd = datetime(y, m, 1).weekday()  # 0=Mon
        first_col   = (first_py_wd + 1) % 7         # 0=Sun

        row, col = 0, first_col

        for day in range(1, days_in_month + 1):
            date_key = f"{y}-{m:02d}-{day:02d}"
            day_dt   = datetime(y, m, day)
            py_wd    = day_dt.weekday()
            sun_wd   = (py_wd + 1) % 7
            is_today = (today.year == y and today.month == m and today.day == day)
            is_past  = day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0)
            is_sel   = self.selected_date == date_key
            is_off   = sun_wd == 0 or sun_wd == 6
            rdv_list = [e for e in self.month_events.get(date_key, []) if _is_real_rdv(e)]
            is_full  = len(rdv_list) >= max_rdv

            if is_sel:
                bg, border_c, border_w = "#dbeafe", C["accent"], 2
            elif is_today:
                bg, border_c, border_w = "#f0f9ff", C["accent"], 2
            elif is_past or is_off:
                bg, border_c, border_w = "#f1f5f9", C["border"], 1
            elif is_full:
                bg, border_c, border_w = "#fef2f2", C["red"], 1
            else:
                bg, border_c, border_w = C["surface"], C["border"], 1

            cell = ctk.CTkFrame(grid_scroll, fg_color=bg, corner_radius=6,
                                border_width=border_w, border_color=border_c)
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            grid_scroll.rowconfigure(row, weight=1)

            # Day number
            label(cell, str(day), size=12, weight="bold",
                  color=C["accent"] if (is_today or is_sel) else
                  (C["text_dim"] if (is_past or is_off) else C["text"])
                  ).pack(anchor="nw", padx=6, pady=(4, 2))

            # RDV preview chips
            if rdv_list and not is_past and not is_off:
                for rdv in rdv_list[:3]:
                    start_h = format_time(rdv.get("start", ""))
                    summary = rdv.get("summary", "")
                    loc     = rdv.get("location", "")
                    name_s  = summary.split("|")[1].strip() if "|" in summary else summary.strip()
                    addr_s  = loc.split(",")[0][:16] if loc else ""

                    chip = ctk.CTkFrame(cell, fg_color="#ffffff", corner_radius=4,
                                        border_width=1,
                                        border_color=C["red"] if is_full else C["green"])
                    chip.pack(fill="x", padx=4, pady=1)

                    top_c = ctk.CTkFrame(chip, fg_color="transparent")
                    top_c.pack(fill="x", padx=4, pady=(3, 0))

                    if start_h:
                        ctk.CTkLabel(top_c, text=start_h,
                                     font=ctk.CTkFont(size=10, weight="bold"),
                                     fg_color=C["red"] if is_full else C["green"],
                                     text_color="white",
                                     corner_radius=3).pack(side="left", padx=(0, 4))

                    ctk.CTkLabel(chip, text=name_s,
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 text_color="#1e293b",
                                 wraplength=220,
                                 justify="left",
                                 anchor="w").pack(anchor="w", padx=6, pady=(2, 0))

                    if addr_s:
                        ctk.CTkLabel(chip, text=f"📍 {addr_s}",
                                     font=ctk.CTkFont(size=11),
                                     text_color="#64748b",
                                     wraplength=220,
                                     justify="left",
                                     anchor="w").pack(anchor="w", padx=6, pady=(0, 4))

                if len(rdv_list) > 3:
                    ctk.CTkLabel(cell, text=f"+ {len(rdv_list)-3} autres",
                                 font=ctk.CTkFont(size=8),
                                 text_color=C["text_muted"]).pack(anchor="w", padx=6, pady=2)

            elif not is_past and not is_off:
                ctk.CTkLabel(cell, text="Libre",
                             font=ctk.CTkFont(size=9),
                             text_color=C["text_dim"]).pack(padx=4, pady=2)

            if not is_past and not is_off:
                cell.bind("<Button-1>", lambda e, dk=date_key: self._select_day(dk))
                for child in cell.winfo_children():
                    child.bind("<Button-1>", lambda e, dk=date_key: self._select_day(dk))
                    for gc in child.winfo_children():
                        gc.bind("<Button-1>", lambda e, dk=date_key: self._select_day(dk))

            col += 1
            if col == 7:
                col = 0
                row += 1

    def _prev_month(self):
        m, y = self.cal_date.month - 1, self.cal_date.year
        if m == 0: m, y = 12, y - 1
        self.cal_date     = self.cal_date.replace(year=y, month=m, day=1)
        self.month_events = {}
        self._render_calendar()
        self._load_calendar()

    def _next_month(self):
        m, y = self.cal_date.month + 1, self.cal_date.year
        if m == 13: m, y = 1, y + 1
        self.cal_date     = self.cal_date.replace(year=y, month=m, day=1)
        self.month_events = {}
        self._render_calendar()
        self._load_calendar()

    # ── Day click ─────────────────────────────────────────────────────────────
    def _select_day(self, date_key):
        self.selected_date = date_key
        self._render_calendar()

    # ── Monthly suggestions ───────────────────────────────────────────────────
    def _show_suggestions_loading(self):
        if self.suggest_frame and self.suggest_frame.winfo_exists():
            self.suggest_frame.destroy()
        self.suggest_frame = ctk.CTkFrame(self.left, fg_color=C["surface2"],
                                           corner_radius=8, border_width=1,
                                           border_color=C["border"])
        self.suggest_frame.pack(fill="x", padx=8, pady=(0, 8))
        label(self.suggest_frame, "⏳  Calcul des meilleures dates...",
              size=12, color=C["text_muted"]).pack(pady=16)

    def _compute_monthly_suggestions(self):
        today   = datetime.today()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        scored  = []

        for date_key, events in self.month_events.items():
            try:
                day_dt  = datetime.strptime(date_key, "%Y-%m-%d")
                weekday = day_dt.weekday()
            except Exception:
                continue
            if day_dt < today.replace(hour=0, minute=0, second=0, microsecond=0):
                continue
            if weekday >= 5:
                continue

            real_rdv = [e for e in events if _is_real_rdv(e)]
            if len(real_rdv) >= max_rdv:
                continue

            taken_hrs = {format_time(e["start"])[:2] for e in real_rdv if format_time(e["start"])}
            free_slots = [(k, v) for k, v in CRENEAUX if k[:2] not in taken_hrs]
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
        self.after(0, self._show_monthly_suggestions, scored[:3])

    def _show_monthly_suggestions(self, suggestions):
        if self.suggest_frame and self.suggest_frame.winfo_exists():
            self.suggest_frame.destroy()

        self.suggest_frame = ctk.CTkFrame(self.left, fg_color=C["surface2"],
                                           corner_radius=8, border_width=1,
                                           border_color=C["border"])
        self.suggest_frame.pack(fill="x", padx=8, pady=(0, 8))

        hdr = ctk.CTkFrame(self.suggest_frame, fg_color="#1e3a5f", corner_radius=8)
        hdr.pack(fill="x")
        label(hdr, "  💡  Meilleures disponibilités", size=13, weight="bold",
              color="#ffffff").pack(side="left", pady=10, padx=8)

        if not suggestions:
            label(self.suggest_frame, "Aucune disponibilité trouvée ce mois-ci.",
                  size=12, color=C["text_muted"]).pack(pady=12)
            return

        rank_colors = ["#16a34a", "#2563eb", "#d97706"]
        medals      = ["🥇", "🥈", "🥉"]

        for i, s in enumerate(suggestions):
            day_parts = s["date_key"].split("-")
            day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]}"
            # weekday in Sun-first format
            py_wd    = s["day_dt"].weekday()
            sun_wd   = (py_wd + 1) % 7
            weekday  = JOURS_FR[sun_wd]

            card = ctk.CTkFrame(self.suggest_frame, fg_color=C["surface"],
                                corner_radius=6, border_width=1, border_color=C["border"])
            card.pack(fill="x", padx=8, pady=4)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=f" #{i+1} ",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         fg_color=rank_colors[i], text_color="white",
                         corner_radius=4).pack(side="left", padx=(0, 8))
            label(top, f"{medals[i]}  {weekday} {day_fmt}  —  {s['slot']}",
                  size=13, weight="bold").pack(side="left")

            det = ctk.CTkFrame(card, fg_color="transparent")
            det.pack(fill="x", padx=10, pady=(0, 4))

            if s["dist_sec"] is not None:
                dist_min = int(s["dist_sec"] // 60)
                rdv_name = s["closest_rdv"].get("summary", "")[:35] if s["closest_rdv"] else ""
                label(det, f"📍 À {dist_min} min d'un RDV existant  •  {s['nb_rdv']} RDV ce jour",
                      size=10, color=C["text_muted"]).pack(anchor="w")
                if rdv_name:
                    label(det, f"   ↳ {rdv_name}", size=10, color=C["text_dim"]).pack(anchor="w")
            else:
                label(det, f"📅 Journée libre  •  {s['nb_rdv']} RDV ce jour",
                      size=10, color=C["text_muted"]).pack(anchor="w")

            ctk.CTkButton(card, text="📋 Copier",
                width=90, height=28, corner_radius=6,
                fg_color=C["accent"], hover_color=C["accent_h"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda s=s: self._copy_suggestion(s)
                ).pack(side="right", padx=10, pady=8)

    def _copy_suggestion(self, s):
        day_parts = s["date_key"].split("-")
        day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]} {day_parts[0]}"
        py_wd     = s["day_dt"].weekday()
        weekday   = JOURS_FR[(py_wd + 1) % 7]
        text = f"{self.rep['nom']} — {s['slot']} — {weekday} {day_fmt} — {self.client_address}"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"📋  Copié : {s['slot']} le {weekday} {day_fmt}")

    # ── Error handlers ────────────────────────────────────────────────────────
    def _hors_territoire(self, city):
        self._clear_rep()
        self._clear_cal()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set(f"Ville : {city}")
        card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                            border_width=1, border_color=C["red"])
        card.pack(fill="x", pady=10)
        label(card, "HORS TERRITOIRE", size=16, weight="bold",
              color=C["red"]).pack(pady=(16, 4))
        label(card, f"La ville {city} n'est pas desservie.",
              size=12, color=C["text_muted"]).pack(pady=(0, 16))

    def _err(self, message):
        self._clear_rep()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set("")
        label(self.rep_frame, message, size=12, color=C["orange"]).pack(pady=20)