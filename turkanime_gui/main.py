import customtkinter as ctk
from turkanime_api.objects import Anime
from turkanime_api.webdriver import create_webdriver
from dosyalar import Dosyalar
import threading

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TurkanimeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Turkanime GUI")
        self.geometry("800x600")

        self.dosyalar = Dosyalar()
        self.driver = create_webdriver()
        self.anime_list = Anime.get_anime_listesi(self.driver)
        self.current_anime = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for slug, title in results:
            anime_button = ctk.CTkButton(
                self.scrollable_frame,
                text=title,
                command=lambda s=slug: self.show_episodes(s)
            )
            anime_button.pack(pady=5, fill="x")

    def show_episodes(self, slug):
        self.current_anime = Anime(self.driver, slug)
        episodes = self.current_anime.bolumler

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        watched_episodes = self.dosyalar.get_gecmis(self.current_anime.slug, "izlendi")

        for bolum in episodes:
            episode_title = bolum.title

            if bolum.slug in watched_episodes:
                display_title = f"{episode_title} ✔"  # Mark as watched
            else:
                display_title = episode_title

            episode_button = ctk.CTkButton(
                self.scrollable_frame,
                text=display_title,
                command=lambda b=bolum: self.play_episode(b)
            )
            episode_button.pack(pady=2, fill="x")

    def play_episode(self, bolum):
        # Run video playback in a separate thread to prevent GUI freezing
        threading.Thread(target=self._play_video, args=(bolum,), daemon=True).start()

    def _play_video(self, bolum):
        video = bolum.best_video()
        if video:
            video.oynat()
            # Mark episode as watched
            self.dosyalar.set_gecmis(self.current_anime.slug, bolum.slug, "izlendi")
            # Update the episode list on the main thread
            self.after(0, self.show_episodes, self.current_anime.slug)

    def on_closing(self):
        self.driver.quit()
        self.destroy()

if __name__ == "__main__":
    app = TurkanimeGUI()
    app.mainloop()
