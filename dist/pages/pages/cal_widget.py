"""
cal_widget.py — Widget calendrier Google partagé
Utilisé par recherche.py et calendrier.py
"""
import customtkinter as ctk
import threading
import calendar
from datetime import datetime
from config import C, label, btn
from google_cal import get_events_for_month, find_calendar_by_name, format_time

MOIS_FR  = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]

SKIP_KEYWORDS  = ["PAS DE RDV", "INDISPONIBLE", "CONGE", "CONGÉ", "FÉRIÉ", "FERIE", "EVITER", "AVOID"]
BLOCK_KEYWORDS = ["PAS DE RDV", "INDISPONIBLE", "CONGE", "CONGÉ", "FÉRIÉ", "FERIE"]
AVOID_KEYWORDS = ["EVITER", "AVOID"]


def is_real_rdv(e):
    if any(x in e.get("summary", "").upper() for x in SKIP_KEYWORDS):
        return False
    # Must have a location OR contain "|" in summary (Ville | Nom format)
    has_location = bool(e.get("location", "").strip())
    has_pipe     = "|" in e.get("summary", "")
    return has_location or has_pipe

def is_blocked_day(events):
    return any(any(x in e.get("summary", "").upper() for x in BLOCK_KEYWORDS) for e in events) \
           and not any(is_real_rdv(e) for e in events)

def get_avoided_slots(events):
    avoided = set()
    for e in events:
        if any(x in e.get("summary", "").upper() for x in AVOID_KEYWORDS):
            h = format_time(e.get("start", ""))
            if h:
                avoided.add(h[:2])
    return avoided

def find_cal_id(rep):
    """Find Google Calendar ID for a rep."""
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


class GoogleCalWidget(ctk.CTkFrame):
    """
    Standalone Google Calendar widget.
    Shows month grid or list view with real Google Calendar data.
    
    Usage:
        widget = GoogleCalWidget(parent, rep, on_day_click=callback)
        widget.pack(fill="both", expand=True)
        widget.load(cal_id)
    """
    def __init__(self, parent, rep, on_day_click=None, max_rdv=5):
        super().__init__(parent, fg_color=C["surface"], corner_radius=8,
                        border_width=1, border_color=C["border"])
        self.rep          = rep
        self.on_day_click = on_day_click
        self.max_rdv      = max_rdv
        self.cal_id       = None
        self.cal_date     = datetime.today().replace(day=1)
        self.month_events = {}
        self.selected     = None
        self.view_mode    = "calendar"
        self._build_skeleton()

    def _build_skeleton(self):
        # Header
        self.hdr = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        self.hdr.pack(fill="x")

        label(self.hdr, f"Calendrier — {self.rep['nom']}",
              size=13, weight="bold").pack(side="left", padx=16, pady=12)

        nav = ctk.CTkFrame(self.hdr, fg_color="transparent")
        nav.pack(side="right", padx=12)
        btn(nav, "<", self._prev, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)
        self.nav_lbl = label(nav, "", size=12, weight="bold", color=C["text"])
        self.nav_lbl.pack(side="left", padx=8)
        btn(nav, ">", self._next, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)

        # Toggle
        toggle = ctk.CTkFrame(self, fg_color=C["surface2"], corner_radius=0)
        toggle.pack(fill="x", padx=8, pady=(4, 0))
        self.btn_cal = ctk.CTkButton(toggle, text="📅  Calendrier",
            width=130, height=30, corner_radius=6,
            fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="white", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._to_calendar)
        self.btn_cal.pack(side="left", padx=6, pady=6)
        self.btn_lst = ctk.CTkButton(toggle, text="☰  Liste",
            width=100, height=30, corner_radius=6,
            fg_color=C["surface"], hover_color=C["accent_h"],
            text_color=C["text_muted"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._to_list)
        self.btn_lst.pack(side="left", padx=2, pady=6)



        # Content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        label(self.content, "Chargement du calendrier...",
              size=12, color=C["text_dim"]).pack(expand=True)

    def load(self, cal_id):
        """Load calendar data for given cal_id."""
        self.cal_id = cal_id
        self._update_nav()
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            y, m = self.cal_date.year, self.cal_date.month
            self.month_events = get_events_for_month(self.cal_id, y, m)
            self.after(0, self._render)
        except Exception:
            self.after(0, self._render)



    def _update_nav(self):
        y, m = self.cal_date.year, self.cal_date.month
        self.nav_lbl.configure(text=f"{MOIS_FR[m]} {y}")

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _to_calendar(self):
        self.view_mode = "calendar"
        self.btn_cal.configure(fg_color=C["accent"], text_color="white")
        self.btn_lst.configure(fg_color=C["surface"], text_color=C["text_muted"])
        self._render()

    def _to_list(self):
        self.view_mode = "list"
        self.btn_cal.configure(fg_color=C["surface"], text_color=C["text_muted"])
        self.btn_lst.configure(fg_color=C["accent"], text_color="white")
        self._render()



    def _prev(self):
        m, y = self.cal_date.month - 1, self.cal_date.year
        if m == 0: m, y = 12, y - 1
        self.cal_date     = self.cal_date.replace(year=y, month=m, day=1)
        self.month_events = {}
        self._update_nav()
        self._render()
        if self.cal_id:
            threading.Thread(target=self._fetch, daemon=True).start()

    def _next(self):
        m, y = self.cal_date.month + 1, self.cal_date.year
        if m == 13: m, y = 1, y + 1
        self.cal_date     = self.cal_date.replace(year=y, month=m, day=1)
        self.month_events = {}
        self._update_nav()
        self._render()
        if self.cal_id:
            threading.Thread(target=self._fetch, daemon=True).start()

    def _render(self):
        self._clear_content()
        if self.view_mode == "calendar":
            self._render_grid()
        else:
            self._render_list()

    # ── Grid view ─────────────────────────────────────────────────────────────
    def _render_grid(self):
        import tkinter as tk
        y, m  = self.cal_date.year, self.cal_date.month
        today = datetime.today()
        _, days_in_month = calendar.monthrange(y, m)

        # Day headers
        hdr = ctk.CTkFrame(self.content, fg_color=C["surface2"], corner_radius=0)
        hdr.pack(fill="x", padx=4)
        hdr.columnconfigure(list(range(7)), weight=1)
        for i, j in enumerate(JOURS_FR):
            label(hdr, j, size=10, weight="bold",
                  color=C["text_muted"]).grid(row=0, column=i, padx=2, pady=5, sticky="nsew")

        # Use a plain frame with grid — scales perfectly
        grid = ctk.CTkFrame(self.content, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=4, pady=4)
        for i in range(7):
            grid.columnconfigure(i, weight=1)

        first_col = (datetime(y, m, 1).weekday() + 1) % 7
        row, col  = 0, first_col
        num_rows  = ((days_in_month + first_col - 1) // 7) + 1
        last_row  = num_rows - 1
        for r in range(num_rows):
            # Last row gets less weight if incomplete
            last_day_col = (first_col + days_in_month - 1) % 7
            is_last = r == last_row
            grid.rowconfigure(r, weight=1 if not is_last else 0, minsize=100)

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
                bg, bc, bw = "#dbeafe", C["accent"], 2
            elif is_today:
                bg, bc, bw = "#f0f9ff", C["accent"], 2
            elif is_past:
                bg, bc, bw = "#f1f5f9", C["border"], 1
            elif blocked:
                bg, bc, bw = "#e2e8f0", "#94a3b8", 1
            elif is_full:
                bg, bc, bw = "#fef2f2", C["red"], 1
            else:
                bg, bc, bw = C["surface"], C["border"], 1

            cell = ctk.CTkFrame(grid, fg_color=bg, corner_radius=6,
                                border_width=bw, border_color=bc)
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

            label(cell, str(day), size=11, weight="bold",
                  color=C["accent"] if (is_today or is_sel) else
                  (C["text_dim"] if is_past else C["text"])
                  ).pack(anchor="nw", padx=4, pady=(3, 1))

            if blocked and not is_past:
                ctk.CTkLabel(cell, text="🚫",
                             font=ctk.CTkFont(size=9),
                             text_color="#94a3b8").pack()
            elif rdv_list and not is_past:
                for rdv in rdv_list[:2]:
                    start_h = format_time(rdv.get("start", ""))
                    summary = rdv.get("summary", "")
                    name_s  = summary.split("|")[1].strip() if "|" in summary else summary.strip()
                    loc     = rdv.get("location", "")
                    addr_s  = loc.split(",")[0][:14] if loc else ""

                    chip = ctk.CTkFrame(cell, fg_color="#ffffff", corner_radius=3,
                                        border_width=1,
                                        border_color=C["red"] if is_full else C["green"])
                    chip.pack(fill="x", padx=3, pady=1)

                    top_c = ctk.CTkFrame(chip, fg_color="transparent")
                    top_c.pack(fill="x", padx=3, pady=(2, 0))

                    if start_h:
                        ctk.CTkLabel(top_c, text=start_h,
                                     font=ctk.CTkFont(size=8, weight="bold"),
                                     fg_color=C["red"] if is_full else C["green"],
                                     text_color="white",
                                     corner_radius=2).pack(side="left", padx=(0, 3))

                    ctk.CTkLabel(chip, text=name_s,
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color="#1e293b",
                                 wraplength=130, justify="left",
                                 anchor="w").pack(anchor="w", padx=3, pady=(1, 0))

                    if addr_s:
                        ctk.CTkLabel(chip, text=f"📍 {addr_s}",
                                     font=ctk.CTkFont(size=9),
                                     text_color="#64748b",
                                     anchor="w").pack(anchor="w", padx=3, pady=(0, 2))

                if len(rdv_list) > 2:
                    ctk.CTkLabel(cell, text=f"+ {len(rdv_list)-2}",
                                 font=ctk.CTkFont(size=8),
                                 text_color=C["text_muted"]).pack(anchor="w", padx=4)
            elif not is_past and not blocked:
                ctk.CTkLabel(cell, text="Libre",
                             font=ctk.CTkFont(size=8),
                             text_color=C["text_dim"]).pack(padx=3, pady=1)

            if not is_past:
                def _click(e, dk=date_key): self._on_click(dk)
                cell.bind("<Button-1>", _click)
                for child in cell.winfo_children():
                    child.bind("<Button-1>", _click)
                    for gc in child.winfo_children():
                        gc.bind("<Button-1>", _click)

            col += 1
            if col == 7:
                col = 0
                row += 1

    # ── List view ─────────────────────────────────────────────────────────────
    def _render_list(self):
        y, m  = self.cal_date.year, self.cal_date.month
        today = datetime.today()
        _, days_in_month = calendar.monthrange(y, m)

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        scroll.bind("<Enter>", lambda e: scroll._parent_canvas.bind_all(
            "<MouseWheel>", lambda ev: scroll._parent_canvas.yview_scroll(
                int(-1*(ev.delta/120)), "units")))
        scroll.bind("<Leave>", lambda e: scroll._parent_canvas.unbind_all("<MouseWheel>"))

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
                bg, bc, bw = "#dbeafe", C["accent"], 2
            elif is_today:
                bg, bc, bw = "#f0f9ff", C["accent"], 2
            elif is_full:
                bg, bc, bw = "#fef2f2", C["red"], 1
            else:
                bg, bc, bw = C["surface"], C["border"], 1

            card = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=10,
                                border_width=bw, border_color=bc)
            card.pack(fill="x", pady=4)

            day_hdr = ctk.CTkFrame(card, fg_color="transparent")
            day_hdr.pack(fill="x", padx=14, pady=(10, 6))

            jour_nom = JOURS_FR[sun_wd]
            ctk.CTkLabel(day_hdr,
                         text=f"{jour_nom}  {day} {MOIS_FR[m]}",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=C["accent"] if (is_today or is_sel) else C["text"]
                         ).pack(side="left")

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

            for rdv in rdv_list:
                start_h = format_time(rdv.get("start", ""))
                summary = rdv.get("summary", "")
                loc     = rdv.get("location", "")
                name_s  = summary.split("|")[1].strip() if "|" in summary else summary.strip()

                row = ctk.CTkFrame(card, fg_color=C["surface2"], corner_radius=6)
                row.pack(fill="x", padx=10, pady=2)
                inner = ctk.CTkFrame(row, fg_color="transparent")
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

                if loc:
                    addr_short = ", ".join(loc.split(",")[:2])[:50]
                    ctk.CTkLabel(inner, text=f"📍 {addr_short}",
                                 font=ctk.CTkFont(size=11),
                                 text_color=C["text_muted"],
                                 anchor="w").pack(anchor="w", pady=(4, 0))

            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

            def _click(e, dk=date_key): self._on_click(dk)
            card.bind("<Button-1>", _click)
            for w in card.winfo_children():
                w.bind("<Button-1>", _click)
                for ww in w.winfo_children():
                    ww.bind("<Button-1>", _click)

    def _on_click(self, date_key):
        self.selected = date_key
        self._render()
        if self.on_day_click:
            self.on_day_click(date_key, self.month_events.get(date_key, []))

    def get_month_events(self):
        return self.month_events

    def get_avoided_slots_for_date(self, date_key):
        return get_avoided_slots(self.month_events.get(date_key, []))