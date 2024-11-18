import customtkinter as ctk
from turkanime_api.objects import Anime
from turkanime_api.webdriver import create_webdriver
from dosyalar import Dosyalar
import threading
from tkinter import messagebox
import os

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
        self.selected_episodes = []

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
        self.selected_episodes = []

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Add Download Button
        self.download_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Seçili Bölümleri İndir",
            command=self.download_selected_episodes
        )
        self.download_button.pack(pady=5)

        watched_episodes = self.dosyalar.get_gecmis(self.current_anime.slug, "izlendi")
        downloaded_episodes = self.dosyalar.get_gecmis(self.current_anime.slug, "indirildi")

        # Episode Checkboxes
        self.episode_vars = []
        for bolum in episodes:
            episode_title = bolum.title

            status = ""
            if bolum.slug in downloaded_episodes:
                status = " (İndirildi)"
            elif bolum.slug in watched_episodes:
                status = " (İzlendi)"

            var = ctk.BooleanVar()
            episode_checkbox = ctk.CTkCheckBox(
                self.scrollable_frame,
                text=episode_title + status,
                variable=var,
                command=lambda b=bolum, v=var: self.on_episode_select(b, v)
            )
            episode_checkbox.pack(anchor="w")
            self.episode_vars.append(var)

            # Play Button
            play_button = ctk.CTkButton(
                self.scrollable_frame,
                text="Oynat",
                width=60,
                command=lambda b=bolum: self.play_episode(b)
            )
            play_button.pack(pady=2)

    def on_episode_select(self, bolum, var):
        if var.get():
            self.selected_episodes.append(bolum)
        else:
            self.selected_episodes.remove(bolum)

    def play_episode(self, bolum):
        threading.Thread(target=self._play_video, args=(bolum,), daemon=True).start()

    def _play_video(self, bolum):
        video = bolum.best_video()
        if video:
            video.oynat()
            # Mark episode as watched
            self.dosyalar.set_gecmis(self.current_anime.slug, bolum.slug, "izlendi")
            # Update the episode list on the main thread
            self.after(0, self.show_episodes, self.current_anime.slug)

    def download_selected_episodes(self):
        if not self.selected_episodes:
            messagebox.showwarning("Uyarı", "Lütfen indirilecek bölümleri seçin.")
            return

        # Create a new window to show download progress
        self.progress_window = ctk.CTkToplevel(self)
        self.progress_window.title("İndirme Durumu")

        self.progress_bars = {}
        for bolum in self.selected_episodes:
            label = ctk.CTkLabel(self.progress_window, text=bolum.title)
            label.pack()
            progress = ctk.CTkProgressBar(self.progress_window)
            progress.set(0)
            progress.pack(pady=5)
            self.progress_bars[bolum.slug] = progress

        threading.Thread(target=self._download_episodes, daemon=True).start()

    def _download_episodes(self):
        for bolum in self.selected_episodes:
            video = bolum.best_video()
            if video:
                # Update progress bar
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                        downloaded_bytes = d.get('downloaded_bytes', 0)
                        if total_bytes:
                            progress = downloaded_bytes / total_bytes
                            self.progress_bars[bolum.slug].set(progress)

                # Prepare output directory
                output_dir = os.path.join(os.getcwd(), "Downloads", self.current_anime.slug)
                os.makedirs(output_dir, exist_ok=True)

                video.indir(callback=progress_hook, output=output_dir)
                # Mark episode as downloaded
                self.dosyalar.set_gecmis(self.current_anime.slug, bolum.slug, "indirildi")
                # Update progress bar to 100%
                self.progress_bars[bolum.slug].set(1.0)
            else:
                messagebox.showerror("Hata", f"{bolum.title} indirilemedi.")

        # Close progress window after downloads complete
        self.after(0, self.progress_window.destroy)
        # Refresh episode list
        self.after(0, self.show_episodes, self.current_anime.slug)

    def on_closing(self):
        self.driver.quit()
        self.destroy()

if __name__ == "__main__":
    app = TurkanimeGUI()
    app.mainloop()
