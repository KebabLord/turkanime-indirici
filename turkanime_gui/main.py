import customtkinter as ctk
from turkanime_api.objects import Anime
from turkanime_api.webdriver import create_webdriver

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TurkanimeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Turkanime GUI")
        self.geometry("800x600")

        # Initialize the driver using create_webdriver
        self.driver = create_webdriver()

        # Fetch the list of anime
        self.anime_list = Anime.get_anime_listesi(self.driver)

        self.create_widgets()

    def create_widgets(self):
        # Search Frame
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(pady=10)

        self.search_entry = ctk.CTkEntry(self.search_frame, width=400, placeholder_text="Anime adı girin")
        self.search_entry.pack(side="left", padx=10)

        self.search_button = ctk.CTkButton(self.search_frame, text="Ara", command=self.search_anime)
        self.search_button.pack(side="left")

        # Results Frame
        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(fill="both", expand=True)

        # Scrollable Canvas for Results
        self.canvas = ctk.CTkCanvas(self.results_frame)
        self.scrollbar = ctk.CTkScrollbar(self.results_frame, command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def search_anime(self):
        query = self.search_entry.get().lower()
        if not query:
            return

        results = [(slug, title) for slug, title in self.anime_list if query in title.lower()]
        self.update_search_results(results)

    def update_search_results(self, results):
        # Clear previous results
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Display new results
        for slug, title in results:
            anime_button = ctk.CTkButton(
                self.scrollable_frame,
                text=title,
                command=lambda s=slug: self.show_episodes(s)
            )
            anime_button.pack(pady=5, fill="x")

    def show_episodes(self, slug):
        anime = Anime(self.driver, slug)
        episodes = anime.bolumler

        # Clear previous episodes/results
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for bolum in episodes:
            episode_title = bolum.title
            # You can mark watched episodes differently here if you have that data
            episode_button = ctk.CTkButton(
                self.scrollable_frame,
                text=episode_title,
                command=lambda b=bolum: self.play_episode(b)
            )
            episode_button.pack(pady=2, fill="x")

    def play_episode(self, bolum):
        video = bolum.best_video()
        if video:
            video.oynat()

if __name__ == "__main__":
    app = TurkanimeGUI()
    app.mainloop()
