import customtkinter as ctk
import webbrowser
import threading
import calendar
from datetime import datetime, timedelta
from config import C, ZONE_COLORS, PRIORITY_LABELS, label, btn
from utils import geocode_address, find_zone, load_rep_rdv, save_rep_rdv, load_zones

CRENEAUX = [
    "9h00 – 10h00",
    "11h00 – 12h00",
    "13h00 – 14h00",
    "15h00 – 16h00",
    "17h00 – 18h00",
]

MOIS_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


class AccueilPage(ctk.CTkFrame):
    def __init__(self, parent, data):
        super().__init__(parent, fg_color=C["bg"])
        self.data      = data
        self.rep       = None   # current P1 rep
        self.rdv       = {}     # rep's rdv data
        self.cal_date  = datetime.today().replace(day=1)
        self.client_address = ""
        self._build()

    def _build(self):
        # Page header
        ph = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        ph.pack(fill="x")
        label(ph, "Recherche de territoire", size=16, weight="bold").pack(side="left", padx=20, pady=14)

        # Main body — 2 columns
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=16)
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=2)
        self.body.rowconfigure(0, weight=1)

        # ── Left: search + rep info ──────────────────────────────────────────
        self.left = ctk.CTkFrame(self.body, fg_color=C["surface"], corner_radius=8,
                                  border_width=1, border_color=C["border"])
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        # Search
        search_card = ctk.CTkFrame(self.left, fg_color=C["surface2"], corner_radius=8)
        search_card.pack(fill="x", padx=14, pady=(14, 10))

        label(search_card, "Adresse du client", size=12,
              color=C["text_muted"]).pack(anchor="w", padx=12, pady=(10, 4))

        row = ctk.CTkFrame(search_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))

        self.entry = ctk.CTkEntry(
            row, placeholder_text="Adresse ou code postal...",
            height=40, font=ctk.CTkFont(size=13), corner_radius=6,
            fg_color=C["surface"], border_color=C["border"]
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._search())

        self.search_btn = btn(row, "Rechercher", self._search, width=120, height=40)
        self.search_btn.pack(side="left")

        self.status_var = ctk.StringVar(value="")
        ctk.CTkLabel(search_card, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11),
                     text_color=C["text_muted"]).pack(anchor="w", padx=12, pady=(0, 6))

        # Rep info area (populated after search)
        self.rep_frame = ctk.CTkScrollableFrame(self.left, fg_color="transparent")
        self.rep_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        label(self.rep_frame,
              "Entrez une adresse pour voir le représentant et son calendrier",
              size=12, color=C["text_dim"]).pack(pady=40)

        # ── Right: calendar ──────────────────────────────────────────────────
        self.right = ctk.CTkFrame(self.body, fg_color=C["surface"], corner_radius=8,
                                   border_width=1, border_color=C["border"])
        self.right.grid(row=0, column=1, sticky="nsew")

        self.cal_placeholder = label(self.right,
                                      "Le calendrier du représentant s'affichera ici",
                                      size=13, color=C["text_dim"])
        self.cal_placeholder.pack(expand=True)

    # ── Search ─────────────────────────────────────────────────────────────────
    def _clear_rep(self):
        for w in self.rep_frame.winfo_children():
            w.destroy()

    def _clear_cal(self):
        for w in self.right.winfo_children():
            w.destroy()

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
        zone, _ = find_zone(city, self.data)
        if zone == "hors_territoire":
            self.after(0, self._hors_territoire, city, full_address)
        elif zone is None:
            self.after(0, self._err, f"Zone non configurée pour : {city}")
        else:
            self.after(0, self._show, zone, city, full_address)

    def _show(self, zone, city, full_address):
        self._clear_rep()
        self._clear_cal()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set(f"Ville détectée : {city}")

        # Find P1 rep
        p1_rep = next((r for r in zone["representants"] if r["priorite"] == 1), None)
        if not p1_rep:
            label(self.rep_frame, "Aucun représentant Priorité 1 trouvé.",
                  size=12, color=C["text_muted"]).pack(pady=20)
            return

        self.rep = p1_rep
        self.rdv = load_rep_rdv(p1_rep["nom"])

        # Map button
        map_frame = ctk.CTkFrame(self.rep_frame, fg_color="transparent")
        map_frame.pack(fill="x", pady=(0, 6))
        btn(map_frame, "🗺  Voir sur la carte", 
            lambda: webbrowser.open(f"https://www.openstreetmap.org/search?query={self.client_address.replace(' ', '+')}"),
            width=200, height=34, color=C["purple"], hover="#6e40c9").pack(side="left")

        # Zone banner
        zone_color = ZONE_COLORS.get(zone["id"], C["accent"])
        banner = ctk.CTkFrame(self.rep_frame, fg_color=zone_color, corner_radius=8)
        banner.pack(fill="x", pady=(4, 8))
        label(banner, f"  {zone['nom'].upper()}", size=13, weight="bold",
              color="#ffffff").pack(side="left", padx=12, pady=8)

        # Rep card
        card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                            border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=(0, 8))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top, text="  PRIORITÉ 1  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     fg_color=C["p1"], text_color="white",
                     corner_radius=4).pack(side="left", padx=(0, 10))
        label(top, p1_rep["nom"], size=15, weight="bold").pack(side="left")

        det = ctk.CTkFrame(card, fg_color="transparent")
        det.pack(fill="x", padx=12, pady=(0, 6))
        label(det, f"📅  {p1_rep['calendrier']}", size=11,
              color=C["accent"], anchor="w").pack(fill="x", pady=1)
        label(det, f"🗓️  {p1_rep['jours']}", size=11,
              color=C["text_muted"], anchor="w").pack(fill="x", pady=1)
        if p1_rep.get("rdv_par_jour"):
            label(det, f"📊  Max {p1_rep['rdv_par_jour']} RDV/jour", size=11,
                  color=C["text_muted"], anchor="w").pack(fill="x", pady=1)

        if p1_rep["regles"]:
            rb = ctk.CTkFrame(card, fg_color=C["bg"], corner_radius=6)
            rb.pack(fill="x", padx=12, pady=(4, 10))
            for r in p1_rep["regles"]:
                label(rb, f"  {r}", size=10, color=C["orange"],
                      anchor="w", wraplength=300, justify="left").pack(fill="x", padx=8, pady=1)
        else:
            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

        # Booking section
        book_frame = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                                   border_width=1, border_color=C["border"])
        book_frame.pack(fill="x", pady=(0, 8))

        label(book_frame, "📍  Adresse à booker", size=12, weight="bold",
              color=C["text_muted"]).pack(anchor="w", padx=12, pady=(10, 4))
        label(book_frame, self.client_address, size=12, weight="bold",
              color=C["text"]).pack(anchor="w", padx=12, pady=(0, 10))

        # Render calendar on the right
        self._render_calendar()

    def _hors_territoire(self, city, full_address):
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

        label(self.right, "Aucun calendrier à afficher",
              size=13, color=C["text_dim"]).pack(expand=True)

    def _err(self, message):
        self._clear_rep()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set("")
        label(self.rep_frame, message, size=12, color=C["orange"]).pack(pady=20)

    # ── Calendar ───────────────────────────────────────────────────────────────
    def _render_calendar(self):
        self._clear_cal()
        if not self.rep:
            return

        y, m = self.cal_date.year, self.cal_date.month
        today = datetime.today()

        # Calendar header
        cal_hdr = ctk.CTkFrame(self.right, fg_color=C["surface"], corner_radius=0)
        cal_hdr.pack(fill="x")

        label(cal_hdr, f"Calendrier — {self.rep['nom']}",
              size=13, weight="bold").pack(side="left", padx=16, pady=12)

        nav = ctk.CTkFrame(cal_hdr, fg_color="transparent")
        nav.pack(side="right", padx=12)
        btn(nav, "<", self._prev_month, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)
        label(nav, f"{MOIS_FR[m]} {y}", size=13, weight="bold", color=C["text"]).pack(side="left", padx=8)
        btn(nav, ">", self._next_month, width=32, height=28,
            color=C["accent"], hover=C["accent_h"]).pack(side="left", padx=2)

        # Day headers
        hdr = ctk.CTkFrame(self.right, fg_color=C["surface2"], corner_radius=0)
        hdr.pack(fill="x", padx=8, pady=(6, 0))
        hdr.columnconfigure(list(range(7)), weight=1)
        for i, j in enumerate(JOURS_FR):
            label(hdr, j, size=11, weight="bold",
                  color=C["text_muted"]).grid(row=0, column=i, padx=2, pady=6, sticky="nsew")

        # Calendar grid
        grid_frame = ctk.CTkFrame(self.right, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=8, pady=4)
        grid_frame.columnconfigure(list(range(7)), weight=1)

        first_weekday, days_in_month = calendar.monthrange(y, m)
        row, col = 0, first_weekday

        for day in range(1, days_in_month + 1):
            date_key = f"{y}-{m:02d}-{day:02d}"
            rdv_list = self.rdv.get(date_key, [])
            is_today = (today.year == y and today.month == m and today.day == day)
            is_past  = datetime(y, m, day) < datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

            # Cell color
            if is_today:
                cell_color  = "#dbeafe"
                border_col  = C["accent"]
                border_w    = 2
            elif is_past:
                cell_color  = C["surface2"]
                border_col  = C["border"]
                border_w    = 1
            elif len(rdv_list) >= (self.rep.get("rdv_par_jour") or 5):
                cell_color  = "#fef2f2"
                border_col  = C["red"]
                border_w    = 1
            else:
                cell_color  = C["surface"]
                border_col  = C["border"]
                border_w    = 1

            cell = ctk.CTkFrame(grid_frame, fg_color=cell_color, corner_radius=6,
                                border_width=border_w, border_color=border_col)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            grid_frame.rowconfigure(row, weight=1)

            # Day number
            label(cell, str(day), size=13, weight="bold",
                  color=C["accent"] if is_today else (C["text_dim"] if is_past else C["text"])
                  ).pack(anchor="nw", padx=6, pady=(4, 0))

            # RDV chips — skip route markers
            real_rdv = [r for r in rdv_list if not r.get("is_route")]
            for idx, rdv in enumerate(real_rdv[:3]):
                chip = ctk.CTkFrame(cell, fg_color=C["green"], corner_radius=3)
                chip.pack(fill="x", padx=4, pady=1)
                heure = rdv.get("heure", "").split("–")[0].strip()
                label(chip, heure, size=9, color="white").pack(side="left", padx=4, pady=2)
                ctk.CTkButton(chip, text="✕", width=16, height=16,
                              corner_radius=3, fg_color="#15803d",
                              hover_color="#166534", font=ctk.CTkFont(size=8),
                              text_color="white",
                              command=lambda dk=date_key, i=idx: self._delete_rdv(dk, i)
                              ).pack(side="right", padx=2)

            if len(real_rdv) > 3:
                label(cell, f"+{len(real_rdv)-3}", size=9,
                      color=C["text_muted"]).pack(anchor="w", padx=6)

            # Route badge
            if any(r.get("is_route") for r in rdv_list):
                ctk.CTkLabel(cell, text="🗺",
                             font=ctk.CTkFont(size=10)).pack(anchor="s", pady=(0,2))

            # Click to book (only future days)
            if not is_past:
                cell.bind("<Button-1>", lambda e, dk=date_key, d=day: self._open_booking(dk, d))

            col += 1
            if col == 7:
                col = 0
                row += 1

        # Legend
        leg = ctk.CTkFrame(self.right, fg_color=C["surface2"], corner_radius=0)
        leg.pack(fill="x", padx=8, pady=(0, 8))
        for color, text in [(C["green"], "RDV booké"), (C["red"], "Journée pleine"), ("#dbeafe", "Aujourd'hui")]:
            dot = ctk.CTkFrame(leg, fg_color=color, width=12, height=12, corner_radius=3)
            dot.pack(side="left", padx=(12, 4), pady=6)
            label(leg, text, size=10, color=C["text_muted"]).pack(side="left", padx=(0, 16))

    def _prev_month(self):
        m, y = self.cal_date.month - 1, self.cal_date.year
        if m == 0:
            m, y = 12, y - 1
        self.cal_date = self.cal_date.replace(year=y, month=m, day=1)
        self._render_calendar()

    def _next_month(self):
        m, y = self.cal_date.month + 1, self.cal_date.year
        if m == 13:
            m, y = 1, y + 1
        self.cal_date = self.cal_date.replace(year=y, month=m, day=1)
        self._render_calendar()

    # ── Delete RDV ────────────────────────────────────────────────────────────
    def _delete_rdv(self, date_key, idx):
        if date_key in self.rdv and idx < len(self.rdv[date_key]):
            rdv = self.rdv[date_key][idx]
            heure = rdv.get("heure", "")
            addr  = rdv.get("adresse", "")[:30]

            dialog = ctk.CTkToplevel(self)
            dialog.title("Supprimer RDV")
            dialog.geometry("380x200")
            dialog.configure(fg_color=C["bg"])
            dialog.lift()
            dialog.focus_force()
            dialog.grab_set()

            hdr = ctk.CTkFrame(dialog, fg_color=C["red"], corner_radius=0)
            hdr.pack(fill="x")
            label(hdr, "  Supprimer ce rendez-vous?",
                  size=13, weight="bold", color="#ffffff").pack(side="left", pady=12, padx=4)

            label(dialog, f"{heure}  —  {addr}",
                  size=12, color=C["text"]).pack(pady=(16, 4))
            label(dialog, "Cette action est irréversible.",
                  size=11, color=C["text_muted"]).pack(pady=(0, 16))

            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.pack()

            def confirm_delete():
                self.rdv[date_key].pop(idx)
                if not self.rdv[date_key]:
                    del self.rdv[date_key]
                save_rep_rdv(self.rep["nom"], self.rdv)
                dialog.destroy()
                self._render_calendar()
                self.status_var.set(f"RDV supprimé.")

            btn(row, "Supprimer", confirm_delete,
                width=140, height=36, color=C["red"], hover="#b02020").pack(side="left", padx=6)
            btn(row, "Annuler", dialog.destroy,
                width=120, height=36, color=C["surface2"], hover=C["border"]).pack(side="left", padx=6)

    # ── Booking dialog ─────────────────────────────────────────────────────────
    def _open_booking(self, date_key, day):
        if not self.rep:
            return

        rdv_list = self.rdv.get(date_key, [])
        max_rdv  = self.rep.get("rdv_par_jour") or 5
        taken    = [r.get("heure") for r in rdv_list]
        free     = [c for c in CRENEAUX if c not in taken]

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Booker — {date_key}")
        dialog.geometry("500x420")
        dialog.configure(fg_color=C["bg"])
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()

        # Header
        hdr = ctk.CTkFrame(dialog, fg_color="#1e3a5f", corner_radius=0)
        hdr.pack(fill="x")
        label(hdr, f"  📅  Booker le {day} {MOIS_FR[self.cal_date.month]}",
              size=14, weight="bold", color="#ffffff").pack(side="left", pady=14, padx=4)

        label(dialog, f"Technicien : {self.rep['nom']}",
              size=12, weight="bold").pack(anchor="w", padx=20, pady=(14, 2))
        label(dialog, f"Adresse : {self.client_address}",
              size=11, color=C["text_muted"]).pack(anchor="w", padx=20, pady=(0, 12))

        # Available slots
        label(dialog, "Créneaux disponibles :", size=12,
              color=C["text_muted"]).pack(anchor="w", padx=20, pady=(0, 6))

        if not free:
            label(dialog, "❌  Journée complète — aucun créneau disponible",
                  size=12, color=C["red"]).pack(pady=20)
            btn(dialog, "Fermer", dialog.destroy,
                width=140, height=36, color=C["surface2"], hover=C["border"]).pack(pady=8)
            return

        # Créneau buttons
        cren_var = ctk.StringVar(value=free[0])
        slot_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        slot_frame.pack(fill="x", padx=20)

        slot_btns = {}

        def select_slot(c):
            cren_var.set(c)
            for k, b in slot_btns.items():
                b.configure(
                    fg_color=C["accent"] if k == c else C["surface2"],
                    text_color="white" if k == c else C["text_muted"]
                )

        for c in free:
            short = c.replace("h00", "h").replace(" – ", "–")
            b = ctk.CTkButton(
                slot_frame, text=short, width=110, height=36,
                corner_radius=6,
                fg_color=C["accent"] if c == free[0] else C["surface2"],
                hover_color=C["accent_h"],
                text_color="white" if c == free[0] else C["text_muted"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda cv=c: select_slot(cv)
            )
            b.pack(side="left", padx=4, pady=4)
            slot_btns[c] = b

        # Already booked
        if taken:
            label(dialog, f"Déjà bookés : {', '.join(t.replace('h00','h').replace(' – ','–') for t in taken)}",
                  size=10, color=C["text_dim"]).pack(anchor="w", padx=20, pady=(4, 0))

        warn_var = ctk.StringVar(value="")
        ctk.CTkLabel(dialog, textvariable=warn_var,
                     font=ctk.CTkFont(size=11),
                     text_color=C["red"]).pack(pady=(8, 0))

        def confirm():
            cren = cren_var.get()
            if date_key not in self.rdv:
                self.rdv[date_key] = []
            self.rdv[date_key].append({
                "heure":   cren,
                "adresse": self.client_address,
            })
            save_rep_rdv(self.rep["nom"], self.rdv)
            dialog.destroy()
            self._render_calendar()
            self.status_var.set(f"✅  RDV booké le {date_key} à {cren} pour {self.rep['nom']}")

        btn(dialog, "✅  Confirmer le RDV", confirm,
            width=240, height=42, color=C["green"], hover=C["green_h"]).pack(pady=(12, 4))
        btn(dialog, "Annuler", dialog.destroy,
            width=120, height=34, color=C["surface2"], hover=C["border"]).pack()