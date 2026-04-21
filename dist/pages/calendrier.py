import customtkinter as ctk
from datetime import datetime
from config import C, label, btn
from pages.cal_widget import GoogleCalWidget, find_cal_id


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
        from pages.cal_widget import show_day_popup
        show_day_popup(self, self.rep, date_key, events)