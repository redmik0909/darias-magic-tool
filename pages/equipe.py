import tkinter as tk
import customtkinter as ctk
from config import C, ZONE_COLORS, PRIORITY_LABELS, label, btn
from utils import get_all_reps
from pages.calendrier import CalendarWindow


class EquipePage(ctk.CTkFrame):
    def __init__(self, parent, data):
        super().__init__(parent, fg_color=C["bg"])
        self.data = data
        self.all_reps = get_all_reps(data)
        self._build()

    def _build(self):
        # Header
        ph = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        ph.pack(fill="x")
        label(ph, "Notre Equipe", size=16, weight="bold").pack(side="left", padx=20, pady=14)
        label(ph, f"{len(self.all_reps)} representants", size=12,
              color=C["text_muted"]).pack(side="left", padx=8)

        # Smooth canvas scroll
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=24, pady=16)

        self.canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Populate zones
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

        for zid, zinfo in zones_seen.items():
            zh = ctk.CTkFrame(self.inner, fg_color=zinfo["couleur"], corner_radius=6)
            zh.pack(fill="x", pady=(14, 4))
            label(zh, f"  {zinfo['nom'].upper()}", size=12, weight="bold",
                  color="#ffffff").pack(side="left", padx=14, pady=7)

            for rep in zinfo["reps"]:
                self._rep_row(rep)

    def refresh(self):
        """Called when switching to this tab — nothing to reload since calendars are popup windows."""
        pass

    def _rep_row(self, rep):
        p_text, p_color = PRIORITY_LABELS.get(rep["priorite"], ("?", C["ov"]))
        card = ctk.CTkFrame(self.inner, corner_radius=6, fg_color=C["surface"],
                            border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=3)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=14, pady=10)

        top_row = ctk.CTkFrame(left, fg_color="transparent")
        top_row.pack(fill="x")
        ctk.CTkLabel(top_row, text=f"  {p_text}  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     fg_color=p_color, text_color="white",
                     corner_radius=4).pack(side="left", padx=(0, 10))
        label(top_row, rep["nom"], size=13, weight="bold").pack(side="left")
        label(left, rep["jours"], size=11, color=C["text_muted"], anchor="w").pack(fill="x", pady=(2, 0))

        btn(card, "Calendrier", lambda r=rep: CalendarWindow(self, r),
            width=110, height=34, color=C["green"], hover=C["green_h"]).pack(side="right", padx=14, pady=10)