import customtkinter as ctk
import calendar
from datetime import datetime, timedelta
from config import C, JOURS_FR, MOIS_FR, label, btn
from utils import load_rep_rdv, save_rep_rdv


class CalendarWindow(ctk.CTkToplevel):
    def __init__(self, parent, rep):
        super().__init__(parent)
        self.rep  = rep
        self.rdv  = load_rep_rdv(rep["nom"])
        self.view = "mois"
        self.current_date = datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.configure(fg_color=C["bg"])
        self.title(f"Calendrier — {rep['nom']}")
        self.geometry("960x680")
        self.minsize(800, 560)
        self.lift()
        self.focus_force()
        self._build()

    def _build(self):
        # Top bar
        top = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        top.pack(fill="x")
        label(top, f"  {self.rep['nom']}", size=15, weight="bold").pack(side="left", padx=10, pady=12)

        toggle = ctk.CTkFrame(top, fg_color="transparent")
        toggle.pack(side="right", padx=14, pady=8)
        self.btn_mois = btn(toggle, "Mois", lambda: self._set_view("mois"), width=80, height=32)
        self.btn_mois.pack(side="left", padx=4)
        self.btn_sem = btn(toggle, "Semaine", lambda: self._set_view("semaine"),
                           width=90, height=32, color=C["surface2"], hover=C["border"])
        self.btn_sem.pack(side="left", padx=4)

        # Nav bar
        nav = ctk.CTkFrame(self, fg_color=C["surface2"], corner_radius=0)
        nav.pack(fill="x")
        btn(nav, "<", self._prev, width=36, height=30, color=C["surface2"], hover=C["border"]).pack(side="left", padx=(14, 4), pady=6)
        self.nav_label = ctk.CTkLabel(nav, text="",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color=C["text"], width=280)
        self.nav_label.pack(side="left", padx=10)
        btn(nav, ">", self._next, width=36, height=30, color=C["surface2"], hover=C["border"]).pack(side="left", padx=4)
        btn(nav, "Aujourd'hui", self._today, width=110, height=30,
            color=C["surface2"], hover=C["border"]).pack(side="left", padx=10)

        # Calendar area
        self.cal_frame = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.cal_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self._render()

    def _set_view(self, view):
        self.view = view
        if view == "mois":
            self.btn_mois.configure(fg_color=C["accent"])
            self.btn_sem.configure(fg_color=C["surface2"])
            self.current_date = self.current_date.replace(day=1)
        else:
            self.btn_mois.configure(fg_color=C["surface2"])
            self.btn_sem.configure(fg_color=C["accent"])
            today = datetime.today()
            self.current_date = today - timedelta(days=today.weekday())
        self._render()

    def _prev(self):
        if self.view == "mois":
            m, y = self.current_date.month - 1, self.current_date.year
            if m == 0: m, y = 12, y - 1
            self.current_date = self.current_date.replace(year=y, month=m, day=1)
        else:
            self.current_date -= timedelta(weeks=1)
        self._render()

    def _next(self):
        if self.view == "mois":
            m, y = self.current_date.month + 1, self.current_date.year
            if m == 13: m, y = 1, y + 1
            self.current_date = self.current_date.replace(year=y, month=m, day=1)
        else:
            self.current_date += timedelta(weeks=1)
        self._render()

    def _today(self):
        today = datetime.today()
        if self.view == "mois":
            self.current_date = today.replace(day=1)
        else:
            self.current_date = today - timedelta(days=today.weekday())
        self._render()

    def _render(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()
        if self.view == "mois":
            self._render_mois()
        else:
            self._render_semaine()

    # ── Vue Mois ───────────────────────────────────────────────────────────────
    def _render_mois(self):
        y, m = self.current_date.year, self.current_date.month
        self.nav_label.configure(text=f"{MOIS_FR[m]}  {y}")
        today = datetime.today()

        hdr = ctk.CTkFrame(self.cal_frame, fg_color=C["surface"], corner_radius=6)
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        hdr.columnconfigure(list(range(7)), weight=1)
        for i, j in enumerate(JOURS_FR):
            label(hdr, j, size=11, weight="bold", color=C["text_muted"]).grid(
                row=0, column=i, padx=2, pady=6, sticky="nsew")

        grid = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=4, pady=4)
        grid.columnconfigure(list(range(7)), weight=1)

        first_weekday, days_in_month = calendar.monthrange(y, m)
        row, col = 0, first_weekday

        for day in range(1, days_in_month + 1):
            date_key = f"{y}-{m:02d}-{day:02d}"
            rdv_list = self.rdv.get(date_key, [])
            count    = len(rdv_list)
            is_today = (today.year == y and today.month == m and today.day == day)

            cell = ctk.CTkFrame(
                grid,
                fg_color=C["surface"] if not is_today else C["surface2"],
                corner_radius=6,
                border_width=2 if is_today else 1,
                border_color=C["accent"] if is_today else C["border"]
            )
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            grid.rowconfigure(row, weight=1)

            label(cell, str(day), size=12, weight="bold",
                  color=C["accent"] if is_today else C["text"]).pack(pady=(6, 2))

            if count > 0:
                ctk.CTkLabel(cell, text=f"{count} RDV",
                             font=ctk.CTkFont(size=10, weight="bold"),
                             fg_color=C["green"], text_color="white",
                             corner_radius=4).pack(padx=6, pady=(0, 6))
            else:
                ctk.CTkFrame(cell, fg_color="transparent", height=4).pack()

            cell.bind("<Button-1>", lambda e, d=day: self._goto_week(d))
            for child in cell.winfo_children():
                child.bind("<Button-1>", lambda e, d=day: self._goto_week(d))

            col += 1
            if col == 7:
                col = 0
                row += 1

    def _goto_week(self, day):
        clicked = datetime(self.current_date.year, self.current_date.month, day)
        self.current_date = clicked - timedelta(days=clicked.weekday())
        self._set_view("semaine")

    # ── Vue Semaine ────────────────────────────────────────────────────────────
    def _render_semaine(self):
        monday = self.current_date
        sunday = monday + timedelta(days=6)
        self.nav_label.configure(
            text=f"{monday.day} {MOIS_FR[monday.month][:3]}. — {sunday.day} {MOIS_FR[sunday.month][:3]}. {sunday.year}"
        )
        today = datetime.today()

        outer = ctk.CTkScrollableFrame(self.cal_frame, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ctk.CTkFrame(outer, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(list(range(7)), weight=1)

        for i in range(7):
            day_dt   = monday + timedelta(days=i)
            date_key = day_dt.strftime("%Y-%m-%d")
            rdv_list = self.rdv.get(date_key, [])
            is_today = (day_dt.date() == today.date())

            hdr = ctk.CTkFrame(cols,
                               fg_color=C["accent"] if is_today else C["surface"],
                               corner_radius=6, border_width=1, border_color=C["border"])
            hdr.grid(row=0, column=i, padx=3, pady=(0, 4), sticky="ew")
            label(hdr, JOURS_FR[i], size=10, weight="bold",
                  color="white" if is_today else C["text_muted"]).pack(pady=(6, 0))
            label(hdr, f"{day_dt.day} {MOIS_FR[day_dt.month][:3]}", size=12, weight="bold",
                  color="white" if is_today else C["text"]).pack(pady=(0, 6))

            col_frame = ctk.CTkFrame(cols, fg_color=C["surface"], corner_radius=6,
                                     border_width=1, border_color=C["border"])
            col_frame.grid(row=1, column=i, padx=3, pady=0, sticky="nsew")
            cols.rowconfigure(1, weight=1)

            for rdv in rdv_list:
                rc = ctk.CTkFrame(col_frame, fg_color=C["green"], corner_radius=4)
                rc.pack(fill="x", padx=4, pady=3)
                if rdv.get("heure"):
                    label(rc, rdv["heure"], size=10, weight="bold", color="white").pack(anchor="w", padx=6, pady=(4, 0))
                label(rc, rdv.get("adresse", ""), size=10, color="white",
                      wraplength=110, justify="left", anchor="w").pack(anchor="w", padx=6, pady=(0, 4))

            if not rdv_list:
                label(col_frame, "—", size=12, color=C["text_dim"]).pack(pady=20)

            btn(col_frame, "+ RDV", lambda dk=date_key: self._add_rdv(dk),
                width=80, height=28, color=C["surface2"], hover=C["border"]).pack(pady=(4, 8))

    # ── Delete RDV ────────────────────────────────────────────────────────────
    def _delete_rdv(self, date_key, idx):
        if date_key in self.rdv and idx < len(self.rdv[date_key]):
            rdv   = self.rdv[date_key][idx]
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
                self._render()

            btn(row, "Supprimer", confirm_delete,
                width=140, height=36, color=C["red"], hover="#b02020").pack(side="left", padx=6)
            btn(row, "Annuler", dialog.destroy,
                width=120, height=36, color=C["surface2"], hover=C["border"]).pack(side="left", padx=6)

    # ── Add RDV ────────────────────────────────────────────────────────────────
    def _add_rdv(self, date_key):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Ajouter RDV — {date_key}")
        dialog.geometry("400x230")
        dialog.configure(fg_color=C["bg"])
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()

        label(dialog, f"Nouveau RDV — {date_key}", size=14, weight="bold").pack(pady=(16, 12))

        label(dialog, "Heure (ex: 9h00)", size=12, color=C["text_muted"]).pack(anchor="w", padx=24)
        heure_e = ctk.CTkEntry(dialog, placeholder_text="9h00", height=36,
                                corner_radius=6, fg_color=C["surface2"], border_color=C["border"])
        heure_e.pack(fill="x", padx=24, pady=(2, 10))

        label(dialog, "Adresse", size=12, color=C["text_muted"]).pack(anchor="w", padx=24)
        adresse_e = ctk.CTkEntry(dialog, placeholder_text="123 rue des Erables, Laval",
                                  height=36, corner_radius=6,
                                  fg_color=C["surface2"], border_color=C["border"])
        adresse_e.pack(fill="x", padx=24, pady=(2, 16))

        def save():
            heure   = heure_e.get().strip()
            adresse = adresse_e.get().strip()
            if not adresse:
                return
            if date_key not in self.rdv:
                self.rdv[date_key] = []
            self.rdv[date_key].append({"heure": heure, "adresse": adresse})
            save_rep_rdv(self.rep["nom"], self.rdv)
            dialog.destroy()
            self._render()

        btn(dialog, "Sauvegarder", save, width=200, height=38,
            color=C["green"], hover=C["green_h"]).pack()