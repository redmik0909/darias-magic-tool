import customtkinter as ctk
import threading
import webbrowser
from datetime import datetime
from config import C, ZONE_COLORS, label, btn
from utils import geocode_address, find_zone, geocode_coords, osrm_route
from google_cal import format_time
from pages.cal_widget import GoogleCalWidget, find_cal_id, is_real_rdv, is_blocked_day, get_avoided_slots, MOIS_FR, JOURS_FR, show_day_popup

CRENEAUX = [
    ("9h00",  "9h00 – 10h00"),
    ("11h00", "11h00 – 12h00"),
    ("13h00", "13h00 – 14h00"),
    ("15h00", "15h00 – 16h00"),
    ("17h00", "17h00 – 18h00"),
]


class RecherchePage(ctk.CTkFrame):
    def __init__(self, parent, data):
        super().__init__(parent, fg_color=C["bg"])
        self.data           = data
        self.rep            = None
        self.cal_widget     = None
        self.client_address = ""
        self.client_coords  = None
        self.suggest_frame  = None
        self.zone_reps      = []
        self.prio_index     = 0
        self._build()

    def _build(self):
        ph = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        ph.pack(fill="x")
        label(ph, "Recherche de territoire", size=16, weight="bold").pack(side="left", padx=20, pady=14)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

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
              "Entrez une adresse pour voir\nle representant et son calendrier",
              size=12, color=C["text_dim"], justify="center").pack(pady=40)

        self.right_container = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                                             border_width=1, border_color=C["border"])
        self.right_container.grid(row=0, column=1, sticky="nsew")
        label(self.right_container, "Le calendrier s affichera ici",
              size=13, color=C["text_dim"]).pack(expand=True)

    def refresh(self):
        if self.cal_widget:
            self.cal_widget.load(self.cal_widget.cal_id)

    def _clear_rep(self):
        for w in self.rep_frame.winfo_children():
            w.destroy()

    def _clear_right(self):
        for w in self.right_container.winfo_children():
            w.destroy()

    # ── Search ────────────────────────────────────────────────────────────────
    def _search(self):
        address = self.entry.get().strip()
        if not address:
            return
        self.client_address = address
        self.search_btn.configure(state="disabled", text="Recherche...")
        self.status_var.set("Geolocalisation en cours...")
        self._clear_rep()
        threading.Thread(target=self._worker, args=(address,), daemon=True).start()

    def _worker(self, address):
        city, full_address = geocode_address(address)
        if not city:
            self.after(0, self._err, "Adresse introuvable")
            return
        # geocode_coords reuses the cached LocationIQ key — fast second call
        coords = geocode_coords(full_address or address)
        if coords:
            self.client_coords = (coords[0], coords[1])
        zone, _ = find_zone(city, self.data)
        if zone == "hors_territoire":
            self.after(0, self._hors_territoire, city)
        elif zone is None:
            self.after(0, self._err, f"Zone non configuree pour : {city}")
        else:
            self.after(0, self._show, zone, city)

    def _show(self, zone, city):
        self._clear_rep()
        self._clear_right()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set(f"Ville detectee : {city}")

        p1_rep = next((r for r in zone["representants"] if r["priorite"] == 1), None)
        if not p1_rep:
            label(self.rep_frame, "Aucun representant Priorite 1.",
                  size=12, color=C["text_muted"]).pack(pady=20)
            return

        self.rep        = p1_rep
        self.zone_reps  = sorted(zone["representants"], key=lambda r: r["priorite"])
        self.prio_index = 0
        self._show_rep_info(zone)

        max_rdv = p1_rep.get("rdv_par_jour") or 5
        self.cal_widget = GoogleCalWidget(
            self.right_container, p1_rep,
            on_day_click=self._on_day_click,
            max_rdv=max_rdv
        )
        self.cal_widget.pack(fill="both", expand=True)

        self._make_suggest_btn()
        threading.Thread(target=self._load_cal, daemon=True).start()

    def _load_cal(self):
        cal_id = find_cal_id(self.rep)
        if cal_id:
            self.after(0, lambda: self.cal_widget.load(cal_id))
        else:
            self.after(0, lambda: self.status_var.set("Calendrier Google non trouve"))

    def _start_suggestions(self):
        if not self.client_coords:
            self.status_var.set("Coordonnees client introuvables.")
            return
        self.suggest_btn.configure(state="disabled", text="Calcul en cours...")
        self._show_suggestions_loading()
        threading.Thread(target=self._compute_suggestions, daemon=True).start()

    # ── Rep info ──────────────────────────────────────────────────────────────
    def _show_rep_info(self, zone):
        self._clear_rep()
        zone_color = ZONE_COLORS.get(zone["id"], C["accent"])

        banner = ctk.CTkFrame(self.rep_frame, fg_color=zone_color, corner_radius=8)
        banner.pack(fill="x", pady=(4, 8))
        label(banner, f"  {zone['nom'].upper()}", size=13, weight="bold",
              color="#ffffff").pack(side="left", padx=12, pady=8)

        nav_row = ctk.CTkFrame(self.rep_frame, fg_color="transparent")
        nav_row.pack(fill="x", pady=(0, 8))

        btn(nav_row, "Voir sur la carte",
            lambda: self._open_map(),
            width=180, height=32, color=C["purple"], hover="#6e40c9").pack(side="left")

        if len(self.zone_reps) > 1:
            next_idx = self.prio_index + 1
            prev_idx = self.prio_index - 1
            if next_idx < len(self.zone_reps):
                btn(nav_row, "→",
                    lambda i=next_idx: self._switch_prio(i),
                    width=40, height=32, color=C["accent"], hover=C["accent_h"]
                    ).pack(side="right")
            if prev_idx >= 0:
                btn(nav_row, "←",
                    lambda i=prev_idx: self._switch_prio(i),
                    width=40, height=32, color=C["accent"], hover=C["accent_h"]
                    ).pack(side="right", padx=(0, 4))

        rep  = self.rep
        card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                            border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=(0, 8))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        prio        = rep["priorite"]
        prio_colors = {1: C["green"], 2: C["orange"], 3: C["red"]}
        prio_color  = prio_colors.get(prio, "#64748b")
        prio_label  = f"PRIORITE {prio}" if prio <= 3 else "AUTRE"
        ctk.CTkLabel(top, text=f"  {prio_label}  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     fg_color=prio_color, text_color="white",
                     corner_radius=4).pack(side="left", padx=(0, 10))
        label(top, rep["nom"], size=15, weight="bold").pack(side="left")

        det = ctk.CTkFrame(card, fg_color="transparent")
        det.pack(fill="x", padx=12, pady=(0, 6))
        label(det, f"  {rep['calendrier']}", size=11, color=C["accent"], anchor="w").pack(fill="x", pady=1)
        label(det, f"  {rep['jours']}", size=11, color=C["text_muted"], anchor="w").pack(fill="x", pady=1)
        if rep.get("rdv_par_jour"):
            label(det, f"  Max {rep['rdv_par_jour']} RDV/jour", size=11,
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
        label(addr_card, "Adresse a booker", size=12, weight="bold",
              color=C["text_muted"]).pack(anchor="w", padx=12, pady=(10, 4))
        label(addr_card, self.client_address, size=12, weight="bold",
              color=C["text"]).pack(anchor="w", padx=12, pady=(0, 10))

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

        if hasattr(self, "suggest_btn") and self.suggest_btn.winfo_exists():
            self.suggest_btn.destroy()
        if self.suggest_frame and self.suggest_frame.winfo_exists():
            self.suggest_frame.destroy()
            self.suggest_frame = None

        self._show_rep_info(zone)

        self._make_suggest_btn()
        self._clear_right()
        max_rdv = self.rep.get("rdv_par_jour") or 5
        self.cal_widget = GoogleCalWidget(
            self.right_container, self.rep,
            on_day_click=self._on_day_click,
            max_rdv=max_rdv
        )
        self.cal_widget.pack(fill="both", expand=True)
        threading.Thread(target=self._load_cal, daemon=True).start()

    def _make_suggest_btn(self):
        if hasattr(self, "suggest_btn") and self.suggest_btn.winfo_exists():
            self.suggest_btn.destroy()
        self.suggest_btn = btn(self.left, "Calculer les suggestions",
            self._start_suggestions,
            width=220, height=36, color=C["green"], hover=C["green_h"])
        self.suggest_btn.pack(padx=8, pady=8)

    # ── Map ────────────────────────────────────────────────────────────────────
    def _open_map(self):
        if self.client_coords:
            lat, lon = self.client_coords
            webbrowser.open(f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16")
        else:
            webbrowser.open(f"https://www.openstreetmap.org/search?query={self.client_address.replace(' ', '+')}")

    # ── Day click ─────────────────────────────────────────────────────────────
    def _on_day_click(self, date_key, events):
        from pages.cal_widget import show_day_popup
        show_day_popup(self, self.rep, date_key, events)

    # ── Suggestions ───────────────────────────────────────────────────────────
    def _show_suggestions_loading(self):
        if self.suggest_frame and self.suggest_frame.winfo_exists():
            self.suggest_frame.destroy()
        self.suggest_frame = ctk.CTkFrame(self.left, fg_color=C["surface2"],
                                           corner_radius=8, border_width=1,
                                           border_color=C["border"])
        self.suggest_frame.pack(fill="x", padx=8, pady=(0, 8))
        label(self.suggest_frame, "Calcul des meilleures dates...",
              size=12, color=C["text_muted"]).pack(pady=16)

    def _compute_suggestions(self):
        if not self.cal_widget:
            return

        today        = datetime.today()
        max_rdv      = self.rep.get("rdv_par_jour") or 5
        scored       = []
        month_events = self.cal_widget.get_month_events()

        for date_key, events in month_events.items():
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
        self.after(0, self._show_suggestions, scored[:3])
        self.after(0, lambda: self.suggest_btn.configure(
            state="normal", text="Recalculer les suggestions"))

    def _show_suggestions(self, suggestions):
        if self.suggest_frame and self.suggest_frame.winfo_exists():
            self.suggest_frame.destroy()

        self.suggest_frame = ctk.CTkFrame(self.left, fg_color=C["surface2"],
                                           corner_radius=8, border_width=1,
                                           border_color=C["border"])
        self.suggest_frame.pack(fill="x", padx=8, pady=(0, 8))

        hdr = ctk.CTkFrame(self.suggest_frame, fg_color="#1e3a5f", corner_radius=8)
        hdr.pack(fill="x")
        label(hdr, "  Meilleures disponibilites", size=13, weight="bold",
              color="#ffffff").pack(side="left", pady=10, padx=8)

        if not suggestions:
            label(self.suggest_frame, "Aucune disponibilite trouvee ce mois-ci.",
                  size=12, color=C["text_muted"]).pack(pady=12)
            return

        rank_colors = ["#16a34a", "#2563eb", "#d97706"]
        medals      = ["#1", "#2", "#3"]

        for i, s in enumerate(suggestions):
            day_parts = s["date_key"].split("-")
            day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]}"
            sun_wd    = (s["day_dt"].weekday() + 1) % 7
            weekday   = JOURS_FR[sun_wd]

            card = ctk.CTkFrame(self.suggest_frame, fg_color=C["surface"],
                                corner_radius=6, border_width=1, border_color=C["border"])
            card.pack(fill="x", padx=8, pady=4)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=f" {medals[i]} ",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         fg_color=rank_colors[i], text_color="white",
                         corner_radius=4).pack(side="left", padx=(0, 8))
            label(top, f"{weekday} {day_fmt}  -  {s['slot']}",
                  size=13, weight="bold").pack(side="left")

            det = ctk.CTkFrame(card, fg_color="transparent")
            det.pack(fill="x", padx=10, pady=(0, 4))

            if s["dist_sec"] is not None:
                dist_min = int(s["dist_sec"] // 60)
                rdv_name = s["closest_rdv"].get("summary", "")[:35] if s["closest_rdv"] else ""
                label(det, f"A {dist_min} min d un RDV existant  -  {s['nb_rdv']} RDV ce jour",
                      size=10, color=C["text_muted"]).pack(anchor="w")
                if rdv_name:
                    label(det, f"   -> {rdv_name}", size=10, color=C["text_dim"]).pack(anchor="w")
            else:
                label(det, f"Journee libre  -  {s['nb_rdv']} RDV ce jour",
                      size=10, color=C["text_muted"]).pack(anchor="w")

            ctk.CTkButton(card, text="Copier",
                width=90, height=28, corner_radius=6,
                fg_color=C["accent"], hover_color=C["accent_h"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda s=s: self._copy(s)
                ).pack(side="right", padx=10, pady=8)

    def _copy(self, s):
        day_parts = s["date_key"].split("-")
        day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]} {day_parts[0]}"
        sun_wd    = (s["day_dt"].weekday() + 1) % 7
        weekday   = JOURS_FR[sun_wd]
        text = f"{self.rep['nom']} - {s['slot']} - {weekday} {day_fmt} - {self.client_address}"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"Copie : {s['slot']} le {weekday} {day_fmt}")

    # ── Errors ────────────────────────────────────────────────────────────────
    def _hors_territoire(self, city):
        self._clear_rep()
        self._clear_right()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set(f"Ville : {city}")
        card = ctk.CTkFrame(self.rep_frame, fg_color=C["surface2"], corner_radius=8,
                            border_width=1, border_color=C["red"])
        card.pack(fill="x", pady=10)
        label(card, "HORS TERRITOIRE", size=16, weight="bold",
              color=C["red"]).pack(pady=(16, 4))
        label(card, f"La ville {city} n est pas desservie.",
              size=12, color=C["text_muted"]).pack(pady=(0, 16))

    def _err(self, message):
        self._clear_rep()
        self.search_btn.configure(state="normal", text="Rechercher")
        self.status_var.set("")
        label(self.rep_frame, message, size=12, color=C["orange"]).pack(pady=20)