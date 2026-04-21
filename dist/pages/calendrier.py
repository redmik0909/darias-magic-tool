import threading
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from config import COLORS
from pages.cal_widget import GoogleCalWidget, find_cal_id, show_day_popup


class CalendarWindow(QMainWindow):
    def __init__(self, rep, parent=None):
        super().__init__(parent)
        self.rep = rep
        self.setWindowTitle(f"Calendrier - {rep['nom']}")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"background-color: {COLORS['bg']};")
        self._build()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        max_rdv = self.rep.get("rdv_par_jour") or 5
        self.cal = GoogleCalWidget(
            self, self.rep,
            on_day_click=self._on_day_click,
            max_rdv=max_rdv
        )
        layout.addWidget(self.cal)

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        cal_id = find_cal_id(self.rep)
        if cal_id:
            self.cal.load(cal_id)

    def _on_day_click(self, date_key, events):
        show_day_popup(self, self.rep, date_key, events)