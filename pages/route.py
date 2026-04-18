import customtkinter as ctk
import tkinter as tk
import threading
import tempfile
import webbrowser
import calendar
from datetime import datetime, timedelta
from config import C, ZONE_COLORS, PRIORITY_LABELS, label, btn
from utils import get_all_reps, osrm_route, decode_polyline, load_rep_rdv, save_rep_rdv

MOIS_FR  = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


class RoutePage(ctk.CTkFrame):
    def __init__(self, parent, data):
        super().__init__(parent, fg_color=C["bg"])
        self.data         = data
        self.all_reps     = get_all_reps(data)
        self.selected_rep = None
        self.selected_date = None
        self.rdv          = {}
        self.cal_date     = datetime.today().replace(day=1)
        self.route_result = None
        self._build()

    # ── Layout ─────────────────────────────────────────────────────────────────
    def _build(self):
        ph = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        ph.pack(fill="x")
        label(ph, "Planification de route", size=16, weight="bold").pack(side="left", padx=20, pady=14)
        self.step_label = label(ph, "Étape 1 — Sélectionnez un technicien",
                                 size=12, color=C["text_muted"])
        self.step_label.pack(side="right", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)

        self._build_rep_panel(body)
        self._build_calendar_panel(body)
        self._build_route_panel(body)

    # ── Panel 1 — Techniciens ──────────────────────────────────────────────────
    def _build_rep_panel(self, body):
        panel = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                             border_width=1, border_color=C["border"])
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        label(panel, "Techniciens", size=13, weight="bold",
              color=C["text_muted"]).pack(anchor="w", padx=14, pady=(14, 8))

        # Group by zone
        zones_seen = {}
        for item in self.all_reps:
            zid  = item["zone"]["id"]
            znom = item["zone"]["nom"]
            if zid not in zones_seen:
                zones_seen[zid] = {
                    "nom": znom,
                    "couleur": ZONE_COLORS.get(zid, C["accent"]),
                    "reps": []
                }
            zones_seen[zid]["reps"].append(item["rep"])

        # Native canvas scroll
        outer = ctk.CTkFrame(panel, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self.rep_buttons = {}
        for zid, zinfo in zones_seen.items():
            zh = ctk.CTkFrame(inner, fg_color=zinfo["couleur"], corner_radius=6)
            zh.pack(fill="x", pady=(8, 2))
            label(zh, f"  {zinfo['nom'].upper()}", size=10, weight="bold",
                  color="#ffffff").pack(side="left", padx=10, pady=5)

            for rep in zinfo["reps"]:
                b = ctk.CTkButton(
                    inner, text=f"  {rep['nom']}", anchor="w",
                    fg_color="transparent", hover_color=C["surface2"],
                    text_color=C["text"], font=ctk.CTkFont(size=12),
                    height=38, corner_radius=6,
                    command=lambda r=rep: self._select_rep(r)
                )
                b.pack(fill="x", pady=1)
                self.rep_buttons[rep["nom"]] = b

    # ── Panel 2 — Calendrier ───────────────────────────────────────────────────
    def _build_calendar_panel(self, body):
        self.cal_panel = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                                       border_width=1, border_color=C["border"])
        self.cal_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))

        label(self.cal_panel,
              "Sélectionnez un\ntechnicien",
              size=13, color=C["text_dim"],
              justify="center").pack(expand=True)

    def _render_calendar(self):
        for w in self.cal_panel.winfo_children():
            w.destroy()

        y, m  = self.cal_date.year, self.cal_date.month
        today = datetime.today()

        # Header
        hdr = ctk.CTkFrame(self.cal_panel, fg_color=C["surface"], corner_radius=0)
        hdr.pack(fill="x", padx=8, pady=(10, 4))

        btn(hdr, "<", self._prev_month, width=30, height=26,
            color=C["accent"], hover=C["accent_h"]).pack(side="left")
        label(hdr, f"{MOIS_FR[m]} {y}", size=12, weight="bold",
              color=C["text"]).pack(side="left", padx=8, expand=True)
        btn(hdr, ">", self._next_month, width=30, height=26,
            color=C["accent"], hover=C["accent_h"]).pack(side="right")

        # Day headers
        dh = ctk.CTkFrame(self.cal_panel, fg_color=C["surface2"], corner_radius=0)
        dh.pack(fill="x", padx=6)
        dh.columnconfigure(list(range(7)), weight=1)
        for i, j in enumerate(JOURS_FR):
            label(dh, j, size=9, weight="bold",
                  color=C["text_muted"]).grid(row=0, column=i, pady=4, sticky="nsew")

        # Grid
        grid = ctk.CTkFrame(self.cal_panel, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=6, pady=4)
        grid.columnconfigure(list(range(7)), weight=1)

        first_weekday, days_in_month = calendar.monthrange(y, m)
        row, col = 0, first_weekday

        for day in range(1, days_in_month + 1):
            date_key = f"{y}-{m:02d}-{day:02d}"
            rdv_list = self.rdv.get(date_key, [])
            is_today = (today.year == y and today.month == m and today.day == day)
            is_past  = datetime(y, m, day) < today.replace(hour=0, minute=0, second=0, microsecond=0)
            is_sel   = self.selected_date == date_key
            has_route = any(r.get("is_route") for r in rdv_list)

            if is_sel:
                bg, border_c, border_w = "#dbeafe", C["accent"], 2
            elif is_today:
                bg, border_c, border_w = "#f0f9ff", C["accent"], 2
            elif is_past:
                bg, border_c, border_w = C["surface2"], C["border"], 1
            else:
                bg, border_c, border_w = C["surface"], C["border"], 1

            cell = ctk.CTkFrame(grid, fg_color=bg, corner_radius=5,
                                border_width=border_w, border_color=border_c)
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            grid.rowconfigure(row, weight=1)

            label(cell, str(day), size=11, weight="bold",
                  color=C["accent"] if (is_today or is_sel) else
                  (C["text_dim"] if is_past else C["text"])).pack(anchor="nw", padx=4, pady=(3, 0))

            if has_route:
                ctk.CTkLabel(cell, text="🗺",
                             font=ctk.CTkFont(size=10)).pack()
            elif rdv_list:
                ctk.CTkLabel(cell,
                             text=f"{len(rdv_list)} RDV",
                             font=ctk.CTkFont(size=9, weight="bold"),
                             fg_color=C["green"], text_color="white",
                             corner_radius=3).pack(padx=3, pady=2)

            cell.bind("<Button-1>", lambda e, dk=date_key: self._select_date(dk))
            for child in cell.winfo_children():
                child.bind("<Button-1>", lambda e, dk=date_key: self._select_date(dk))

            col += 1
            if col == 7:
                col = 0
                row += 1

    def _prev_month(self):
        m, y = self.cal_date.month - 1, self.cal_date.year
        if m == 0: m, y = 12, y - 1
        self.cal_date = self.cal_date.replace(year=y, month=m, day=1)
        self._render_calendar()

    def _next_month(self):
        m, y = self.cal_date.month + 1, self.cal_date.year
        if m == 13: m, y = 1, y + 1
        self.cal_date = self.cal_date.replace(year=y, month=m, day=1)
        self._render_calendar()

    # ── Panel 3 — Route ────────────────────────────────────────────────────────
    def _build_route_panel(self, body):
        self.route_panel = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=8,
                                         border_width=1, border_color=C["border"])
        self.route_panel.grid(row=0, column=2, sticky="nsew")

        self.route_placeholder = label(self.route_panel,
                                        "Sélectionnez un technicien\npuis une journée",
                                        size=13, color=C["text_dim"], justify="center")
        self.route_placeholder.pack(expand=True)

    def _render_route_panel(self):
        for w in self.route_panel.winfo_children():
            w.destroy()

        if not self.selected_date or not self.selected_rep:
            return

        rdv_list = self.rdv.get(self.selected_date, [])
        date_fmt  = self.selected_date

        # Header
        hdr = ctk.CTkFrame(self.route_panel, fg_color="#1e3a5f", corner_radius=0)
        hdr.pack(fill="x")
        label(hdr, f"  {self.selected_rep['nom']}  —  {date_fmt}",
              size=13, weight="bold", color="#ffffff").pack(side="left", pady=12, padx=8)

        if not rdv_list:
            label(self.route_panel,
                  "Aucun RDV ce jour.\nBookez des RDV depuis l'onglet Accueil.",
                  size=12, color=C["text_dim"], justify="center").pack(expand=True)
            return

        # Sort by créneau
        def sort_key(r):
            h = r.get("heure", "")
            order = {"9h00": 0, "11h00": 1, "13h00": 2, "15h00": 3, "17h00": 4}
            for k, v in order.items():
                if k in h:
                    return v
            return 99

        rdv_sorted = sorted([r for r in rdv_list if not r.get("is_route")], key=sort_key)

        # RDV list
        label(self.route_panel, f"  {len(rdv_sorted)} rendez-vous ce jour :",
              size=12, weight="bold", color=C["text_muted"]).pack(anchor="w", pady=(10, 4))

        scroll = ctk.CTkScrollableFrame(self.route_panel, fg_color="transparent", height=260)
        scroll.pack(fill="x", padx=10)

        self.rdv_display = rdv_sorted
        for i, rdv in enumerate(rdv_sorted):
            card = ctk.CTkFrame(scroll, fg_color=C["surface2"], corner_radius=6,
                                border_width=1, border_color=C["border"])
            card.pack(fill="x", pady=3)

            ctk.CTkLabel(card, text=f" {i+1} ",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         fg_color=C["accent"], text_color="white",
                         corner_radius=4, width=26).pack(side="left", padx=(8, 8), pady=8)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, pady=6)

            heure = rdv.get("heure", "").replace("h00", "h").replace(" – ", "–")
            label(info, heure, size=11, weight="bold",
                  color=C["accent"], anchor="w").pack(anchor="w")
            label(info, rdv.get("adresse", ""), size=11,
                  color=C["text"], anchor="w", wraplength=300).pack(anchor="w")

        # Check if route already created
        has_route = any(r.get("is_route") for r in rdv_list)

        if has_route:
            done = ctk.CTkFrame(self.route_panel, fg_color="#f0fdf4", corner_radius=8,
                                border_width=1, border_color=C["green"])
            done.pack(fill="x", padx=10, pady=8)
            label(done, "🗺  Route créée pour cette journée",
                  size=13, weight="bold", color=C["green"]).pack(pady=(12, 4))
            label(done, "Visible dans le calendrier du technicien.",
                  size=11, color=C["text_muted"]).pack(pady=(0, 12))

            btn(self.route_panel, "Voir sur la carte", self._open_map,
                width=180, height=36, color=C["purple"], hover="#6e40c9").pack(pady=(0, 8))
            btn(self.route_panel, "Recréer la route", self._generate_route,
                width=180, height=36, color=C["surface2"], hover=C["border"]).pack(pady=(0, 10))
        else:
            btn(self.route_panel, "🗺  Optimiser & Créer la route",
                self._generate_route,
                width=240, height=44, color=C["accent"], hover=C["accent_h"]).pack(pady=16)

    def refresh(self):
        """Called when switching to this tab — reload RDV if a rep is selected."""
        if self.selected_rep:
            self.rdv = load_rep_rdv(self.selected_rep["nom"])
            self._render_calendar()
            if self.selected_date:
                self._render_route_panel()

    # ── Selection ──────────────────────────────────────────────────────────────
    def _select_rep(self, rep):
        self.selected_rep  = rep
        self.selected_date = None
        self.rdv           = load_rep_rdv(rep["nom"])
        self.route_result  = None

        # Highlight selected button
        for name, b in self.rep_buttons.items():
            b.configure(
                fg_color=C["accent"] if name == rep["nom"] else "transparent",
                text_color="white" if name == rep["nom"] else C["text"],
                font=ctk.CTkFont(size=12, weight="bold" if name == rep["nom"] else "normal")
            )

        self.step_label.configure(text="Étape 2 — Choisissez une journée")
        self._render_calendar()

        # Clear route panel
        for w in self.route_panel.winfo_children():
            w.destroy()
        label(self.route_panel,
              "Choisissez une journée\ndans le calendrier",
              size=13, color=C["text_dim"], justify="center").pack(expand=True)

    def _select_date(self, date_key):
        self.selected_date = date_key
        self.route_result  = None
        self.step_label.configure(text="Étape 3 — Créez la route")
        self._render_calendar()
        self._render_route_panel()

    # ── Route generation ───────────────────────────────────────────────────────
    def _generate_route(self):
        if not self.selected_date or not self.selected_rep:
            return

        rdv_list = [r for r in self.rdv.get(self.selected_date, []) if not r.get("is_route")]
        if len(rdv_list) < 2:
            for w in self.route_panel.winfo_children():
                w.destroy()
            label(self.route_panel,
                  "Il faut au moins 2 RDV\npour créer une route.",
                  size=13, color=C["orange"], justify="center").pack(expand=True)
            return

        self.step_label.configure(text="Calcul en cours...")

        # Show spinner
        for w in self.route_panel.winfo_children():
            w.destroy()
        label(self.route_panel, "⏳  Optimisation en cours...",
              size=14, color=C["text_muted"]).pack(expand=True)

        threading.Thread(target=self._worker_route, args=(rdv_list,), daemon=True).start()

    def _worker_route(self, rdv_list):
        from utils import geocode_coords

        # Geocode all addresses
        coords = []
        for rdv in rdv_list:
            result = geocode_coords(rdv.get("adresse", ""))
            if result:
                coords.append((result[0], result[1]))
            else:
                coords.append(None)

        # Filter out None
        valid = [(i, c) for i, c in enumerate(coords) if c is not None]
        if len(valid) < 2:
            self.after(0, lambda: self._show_route_error("Impossible de géocoder les adresses."))
            return

        valid_indices = [i for i, _ in valid]
        valid_coords  = [c for _, c in valid]

        durations, order, total_sec, geometry = osrm_route(valid_coords)
        if durations is None:
            self.after(0, lambda: self._show_route_error("Erreur OSRM — vérifiez la connexion."))
            return

        # Map order back to original rdv indices
        ordered_rdv = [rdv_list[valid_indices[i]] for i in order]
        ordered_coords = [valid_coords[i] for i in order]

        self.after(0, self._show_route_result,
                   ordered_rdv, ordered_coords, durations, order, total_sec, geometry)

    def _show_route_error(self, msg):
        for w in self.route_panel.winfo_children():
            w.destroy()
        label(self.route_panel, msg, size=13, color=C["red"],
              justify="center").pack(expand=True)
        self.step_label.configure(text="Étape 3 — Créez la route")

    def _show_route_result(self, ordered_rdv, ordered_coords, durations, order, total_sec, geometry):
        self.route_result = {
            "ordered_rdv":    ordered_rdv,
            "ordered_coords": ordered_coords,
            "geometry":       geometry,
            "durations":      durations,
            "order":          order,
        }

        for w in self.route_panel.winfo_children():
            w.destroy()

        # Header
        hdr = ctk.CTkFrame(self.route_panel, fg_color="#1e3a5f", corner_radius=0)
        hdr.pack(fill="x")
        label(hdr, f"  Route optimisée — {self.selected_date}",
              size=13, weight="bold", color="#ffffff").pack(side="left", pady=12, padx=8)

        if total_sec:
            label(hdr, f"{int(total_sec//60)} min  ",
                  size=11, color="#93c5fd").pack(side="right", padx=8)

        # Ordered stops
        scroll = ctk.CTkScrollableFrame(self.route_panel, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=8)

        for step, rdv in enumerate(ordered_rdv):
            stop = ctk.CTkFrame(scroll, fg_color=C["surface2"], corner_radius=8,
                                border_width=1, border_color=C["border"])
            stop.pack(fill="x", pady=4)

            ctk.CTkLabel(stop, text=f"  {step+1}  ",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         fg_color=C["accent"], text_color="white",
                         corner_radius=4, width=30).pack(side="left", padx=(8, 8), pady=10)

            info = ctk.CTkFrame(stop, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, pady=8)

            heure = rdv.get("heure", "").replace("h00", "h").replace(" – ", "–")
            label(info, heure, size=11, weight="bold",
                  color=C["accent"], anchor="w").pack(anchor="w")
            label(info, rdv.get("adresse", ""), size=11,
                  color=C["text"], anchor="w", wraplength=300).pack(anchor="w")

            # Time to next
            if step < len(ordered_rdv) - 1:
                d_min = int(durations[order[step]][order[step+1]] // 60) if durations else 0
                label(stop, f"{d_min} min →", size=10, weight="bold",
                      color=C["green"]).pack(side="right", padx=10)

        # Buttons
        bar = ctk.CTkFrame(self.route_panel, fg_color=C["surface2"],
                           corner_radius=0, border_width=1, border_color=C["border"])
        bar.pack(fill="x")

        btn(bar, "Voir sur la carte", self._open_map,
            width=160, height=36, color=C["purple"], hover="#6e40c9").pack(side="left", padx=10, pady=8)

        btn(bar, "✅  Sauvegarder la route", self._save_route,
            width=200, height=36, color=C["green"], hover=C["green_h"]).pack(side="right", padx=10, pady=8)

        self.step_label.configure(text="Route optimisée — sauvegardez!")

    def _save_route(self):
        if not self.route_result or not self.selected_date:
            return

        # Mark route as created in rdv data
        date_key = self.selected_date
        if date_key not in self.rdv:
            self.rdv[date_key] = []

        # Remove old route marker if exists
        self.rdv[date_key] = [r for r in self.rdv[date_key] if not r.get("is_route")]

        # Add route marker
        self.rdv[date_key].append({
            "is_route": True,
            "ordre":    [r.get("adresse") for r in self.route_result["ordered_rdv"]],
        })

        save_rep_rdv(self.selected_rep["nom"], self.rdv)
        self.step_label.configure(text="✅  Route sauvegardée!")
        self._render_calendar()
        self._render_route_panel()

    # ── Map ────────────────────────────────────────────────────────────────────
    def _open_map(self):
        if not self.route_result:
            return

        ordered_rdv    = self.route_result["ordered_rdv"]
        ordered_coords = self.route_result["ordered_coords"]
        geometry       = self.route_result.get("geometry")

        route_coords = decode_polyline(geometry) if geometry else []

        if route_coords:
            coords_js = str([[lat, lon] for lat, lon in route_coords])
            route_js  = f"L.polyline({coords_js}, {{color:'#2563eb',weight:4,opacity:0.8}}).addTo(map);"
        else:
            latlngs  = [[c[0], c[1]] for c in ordered_coords]
            route_js = f"L.polyline({latlngs}, {{color:'#2563eb',weight:3,dashArray:'8,6',opacity:0.7}}).addTo(map);"

        markers_js = ""
        for i, (rdv, coord) in enumerate(zip(ordered_rdv, ordered_coords)):
            heure = rdv.get("heure", "").replace("h00", "h").replace(" – ", "–")
            addr  = rdv.get("adresse", "")
            markers_js += f"""
        L.circleMarker([{coord[0]},{coord[1]}],{{radius:16,fillColor:'#2563eb',color:'#fff',weight:2,fillOpacity:0.9}})
         .addTo(map).bindTooltip('{i+1}',{{permanent:true,className:'stop-label',direction:'center'}});
        L.marker([{coord[0]},{coord[1]}]).addTo(map)
         .bindPopup('<b>Arrêt {i+1}</b><br><i>{heure}</i><br>{addr}');
"""

        stops_html = ""
        for i, rdv in enumerate(ordered_rdv):
            heure  = rdv.get("heure", "").replace("h00", "h").replace(" – ", "–")
            addr   = rdv.get("adresse", "")
            arrow  = "" if i == len(ordered_rdv)-1 else '<div class="arrow">↓</div>'
            stops_html += f"""
            <div class="stop">
                <div class="num">{i+1}</div>
                <div>
                    <div class="cren">{heure}</div>
                    <div class="addr">{addr}</div>
                </div>
            </div>{arrow}"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Route — {self.selected_rep['nom'] if self.selected_rep else ''}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f0f4f8;display:flex;height:100vh;}}
#sidebar{{width:300px;background:#fff;border-right:1px solid #cfd8e3;overflow-y:auto;flex-shrink:0;}}
#sidebar h2{{padding:14px 16px;font-size:14px;border-bottom:1px solid #e2e8f0;
             background:#1e3a5f;color:#fff;}}
.stop{{padding:10px 16px;border-bottom:1px solid #f1f5f9;
       display:flex;align-items:flex-start;gap:10px;}}
.stop:hover{{background:#f8fafc;}}
.num{{background:#2563eb;color:white;border-radius:50%;width:28px;height:28px;
      display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:13px;flex-shrink:0;}}
.cren{{font-size:11px;color:#2563eb;font-weight:600;margin-bottom:2px;}}
.addr{{font-size:12px;color:#1e293b;}}
.arrow{{padding:2px 16px;font-size:14px;color:#94a3b8;}}
#map{{flex:1;}}
.stop-label{{background:transparent!important;border:none!important;
             box-shadow:none!important;color:white;font-weight:bold;font-size:12px;}}
</style></head>
<body>
<div id="sidebar">
  <h2>🗺  Route — {self.selected_date}</h2>
  {stops_html}
</div>
<div id="map"></div>
<script>
var map=L.map('map').setView([{ordered_coords[0][0]},{ordered_coords[0][1]}],12);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{
  attribution:'© OpenStreetMap'}}).addTo(map);
{route_js}
{markers_js}
</script></body></html>"""

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file://{tmp.name}")