import customtkinter as ctk
from datetime import datetime
from config import C, label

JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_FR  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


class AccueilPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C["bg"])
        self._build()

    def _build(self):
        # Center everything
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Big greeting
        now     = datetime.now()
        jour    = JOURS_FR[now.weekday()]
        date    = f"{jour} {now.day} {MOIS_FR[now.month]} {now.year}"
        heure   = now.strftime("%H:%M")

        # Logo / icon
        ctk.CTkLabel(center, text="✨",
                     font=ctk.CTkFont(size=72),
                     text_color=C["accent"]).pack(pady=(0, 10))

        # Main message
        ctk.CTkLabel(center,
                     text="Bonjour Daria!",
                     font=ctk.CTkFont(size=48, weight="bold"),
                     text_color=C["text"]).pack()

        ctk.CTkLabel(center,
                     text="Ton twin te souhaite un bon shift 💪",
                     font=ctk.CTkFont(size=22),
                     text_color=C["text_muted"]).pack(pady=(8, 24))

        # Date & time card
        date_card = ctk.CTkFrame(center, fg_color=C["surface"], corner_radius=12,
                                  border_width=1, border_color=C["border"])
        date_card.pack(pady=(0, 24), padx=40, fill="x")

        ctk.CTkLabel(date_card,
                     text=date,
                     font=ctk.CTkFont(size=16),
                     text_color=C["text_muted"]).pack(pady=(16, 4))

        ctk.CTkLabel(date_card,
                     text=heure,
                     font=ctk.CTkFont(size=42, weight="bold"),
                     text_color=C["purple"]).pack(pady=(0, 16))

        # Tip
        ctk.CTkLabel(center,
                     text="👉  Utilise l'onglet Recherche pour trouver le bon technicien",
                     font=ctk.CTkFont(size=14),
                     text_color=C["text_dim"]).pack()

    def refresh(self):
        """Refresh clock on tab switch."""
        for w in self.winfo_children():
            w.destroy()
        self._build()