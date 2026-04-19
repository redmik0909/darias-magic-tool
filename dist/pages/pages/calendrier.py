import customtkinter as ctk
from datetime import datetime
from config import C, label, btn
from pages.cal_widget import GoogleCalWidget, find_cal_id, MOIS_FR


class CalendarWindow(ctk.CTkToplevel):
    def __init__(self, parent, rep):
        super().__init__(parent)
        self.rep = rep
        self.configure(fg_color=C["bg"])
        self.title(f"Calendrier - {rep['nom']}")
        # Open maximized
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.after(100, lambda: self.state("zoomed"))
        self.minsize(800, 560)
        self.lift()
        self.focus_force()
        self._build()

    def _build(self):
        # Calendar widget
        max_rdv = self.rep.get("rdv_par_jour") or 5
        self.cal = GoogleCalWidget(
            self, self.rep,
            on_day_click=self._on_day_click,
            max_rdv=max_rdv
        )
        self.cal.pack(fill="both", expand=True, padx=10, pady=10)

        # Load Google Calendar
        import threading
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        cal_id = find_cal_id(self.rep)
        if cal_id:
            self.after(0, lambda: self.cal.load(cal_id))
        else:
            self.after(0, lambda: label(self.cal, "Calendrier Google non trouve",
                                        size=12, color=C["orange"]).pack(pady=20))

    def _on_day_click(self, date_key, events):
        """Show day detail popup."""
        from google_cal import format_time
        from pages.cal_widget import is_real_rdv

        day_parts = date_key.split("-")
        day_fmt   = f"{int(day_parts[2])} {MOIS_FR[int(day_parts[1])]} {day_parts[0]}"
        real_rdv  = [e for e in events if is_real_rdv(e)]

        popup = ctk.CTkToplevel(self)
        popup.title(f"RDV - {day_fmt}")
        popup.geometry("500x420")
        popup.configure(fg_color=C["bg"])
        popup.attributes("-topmost", True)
        popup.lift()
        popup.focus_force()

        hdr = ctk.CTkFrame(popup, fg_color="#1e3a5f", corner_radius=0)
        hdr.pack(fill="x")
        label(hdr, f"  {day_fmt} - {self.rep['nom']}",
              size=14, weight="bold", color="#ffffff").pack(side="left", pady=12, padx=8)
        label(hdr, f"{len(real_rdv)} RDV  ",
              size=12, color="#93c5fd").pack(side="right", padx=8)

        if not real_rdv:
            label(popup, "Aucun RDV ce jour - journee libre!",
                  size=13, color=C["green"]).pack(expand=True)
        else:
            scroll = ctk.CTkScrollableFrame(popup, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=12, pady=12)
            for e in real_rdv:
                card = ctk.CTkFrame(scroll, fg_color=C["surface2"], corner_radius=6,
                                    border_width=1, border_color=C["border"])
                card.pack(fill="x", pady=4)
                time_str = format_time(e["start"])
                top_r    = ctk.CTkFrame(card, fg_color="transparent")
                top_r.pack(fill="x", padx=12, pady=(8, 2))
                ctk.CTkLabel(top_r, text=f" {time_str} ",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             fg_color=C["accent"], text_color="white",
                             corner_radius=4).pack(side="left", padx=(0, 8))
                label(top_r, e.get("summary", "Sans titre"), size=12,
                      weight="bold").pack(side="left")
                if e.get("location"):
                    label(card, f"   {e['location']}", size=11,
                          color=C["text_muted"], anchor="w",
                          wraplength=440).pack(anchor="w", padx=12, pady=(0, 8))
                else:
                    ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

        btn(popup, "Fermer", popup.destroy,
            width=120, height=34, color=C["surface2"],
            hover=C["border"]).pack(pady=(0, 12))