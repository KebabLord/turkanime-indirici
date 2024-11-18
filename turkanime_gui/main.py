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
        self.geometry("900x700")

        self.dosyalar = Dosyalar()
        self.driver = create_webdriver()
        self.anime_list = Anime.get_anime_listesi(self.driver)
        self.current_anime = None
        self.selected_episodes = []
        self.download_threads = {}
        self.download_controls = {}

        self.items_per_page = 20  # Customizable count of anime displayed per page
        self.current_page = 0
        self.search_results = self.anime_list  # Initialize search results with full anime list

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Show the anime list on launch
        self.update_search_results()

    def create_widgets(self):
        # Search Frame
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(pady=10, fill="x")

        self.search_entry = ctk.CTkEntry(self.search_frame, width=400, placeholder_text="Anime adı girin")
        self.search_entry.pack(side="left", padx=10, fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda event: self.search_anime())
        self.search_entry.bind("<KeyRelease>", self.on_key_release)

        self.search_button = ctk.CTkButton(self.search_frame, text="Ara", command=self.search_anime)
        self.search_button.pack(side="left", padx=10)

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

        # Pagination Controls
        self.pagination_frame = ctk.CTkFrame(self)
        self.pagination_frame.pack(pady=5)

        self.prev_button = ctk.CTkButton(self.pagination_frame, text="Önceki", command=self.prev_page)
        self.prev_button.pack(side="left", padx=5)

        self.page_label = ctk.CTkLabel(self.pagination_frame, text=f"Sayfa {self.current_page + 1}")
        self.page_label.pack(side="left", padx=5)

        self.next_button = ctk.CTkButton(self.pagination_frame, text="Sonraki", command=self.next_page)
        self.next_button.pack(side="left", padx=5)

    def on_key_release(self, event):
        # Immediate search on key release
        self.search_anime()

    def search_anime(self):
        query = self.search_entry.get().lower()
        if not query:
            # Show full anime list if no search query
            self.search_results = self.anime_list
        else:
            # Filter anime list based on query
            self.search_results = [(slug, title) for slug, title in self.anime_list if query in title.lower()]
        self.current_page = 0  # Reset to first page after search
        self.update_search_results()

    def update_search_results(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        results = self.search_results

        # Pagination
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_results = results[start_index:end_index]

        for slug, title in paginated_results:
            anime_button = ctk.CTkButton(
                self.scrollable_frame,
                text=title,
                command=lambda s=slug: self.show_episodes(s)
            )
            anime_button.pack(pady=5, fill="x")

        # Update pagination label
        total_pages = len(results) // self.items_per_page + (1 if len(results) % self.items_per_page > 0 else 0)
        if total_pages == 0:
            total_pages = 1  # Avoid division by zero
        self.page_label.configure(text=f"Sayfa {self.current_page + 1} / {total_pages}")
        self.prev_button.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_search_results()

    def next_page(self):
        total_pages = len(self.search_results) // self.items_per_page + (1 if len(self.search_results) % self.items_per_page > 0 else 0)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_search_results()

    def show_episodes(self, slug):
        self.current_anime = Anime(self.driver, slug)
        episodes = self.current_anime.bolumler
        self.selected_episodes = []
        self.download_threads = {}
        self.download_controls = {}

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
            episode_frame = ctk.CTkFrame(self.scrollable_frame)
            episode_frame.pack(fill="x", pady=2)

            episode_title = bolum.title

            status = ""
            if bolum.slug in downloaded_episodes:
                status = " (İndirildi)"
            elif bolum.slug in watched_episodes:
                status = " (İzlendi)"

            var = ctk.BooleanVar()
            episode_checkbox = ctk.CTkCheckBox(
                episode_frame,
                text=episode_title + status,
                variable=var,
                command=lambda b=bolum, v=var: self.on_episode_select(b, v)
            )
            episode_checkbox.pack(side="left", padx=5)
            self.episode_vars.append(var)

            # Play Button
            play_button = ctk.CTkButton(
                episode_frame,
                text="Oynat",
                width=60,
                command=lambda b=bolum: self.play_episode(b)
            )
            play_button.pack(side="right", padx=5)

        # Live Search within episodes
        self.episode_search_entry = ctk.CTkEntry(self.scrollable_frame, width=400, placeholder_text="Bölüm adı ara")
        self.episode_search_entry.pack(pady=5)
        self.episode_search_entry.bind("<KeyRelease>", self.on_episode_search)

    def on_episode_search(self, event):
        query = self.episode_search_entry.get().lower()
        for i, bolum in enumerate(self.current_anime.bolumler):
            episode_frame = self.scrollable_frame.winfo_children()[i + 2]  # +2 to skip the download button and search entry
            if query in bolum.title.lower():
                episode_frame.pack(fill="x", pady=2)
            else:
                episode_frame.forget()

    def on_episode_select(self, bolum, var):
        if var.get():
            self.selected_episodes.append(bolum)
        else:
            if bolum in self.selected_episodes:
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
            frame = ctk.CTkFrame(self.progress_window)
            frame.pack(fill="x", pady=5)

            label = ctk.CTkLabel(frame, text=bolum.title)
            label.pack(side="left")

            progress = ctk.CTkProgressBar(frame)
            progress.set(0)
            progress.pack(side="left", fill="x", expand=True, padx=5)
            self.progress_bars[bolum.slug] = progress

            pause_button = ctk.CTkButton(frame, text="Duraklat", width=70,
                                         command=lambda b=bolum: self.pause_download(b))
            pause_button.pack(side="right", padx=5)
            self.download_controls[bolum.slug] = {'paused': False, 'pause_button': pause_button}

        threading.Thread(target=self._download_episodes, daemon=True).start()

    def _download_episodes(self):
        for bolum in self.selected_episodes:
            video = bolum.best_video()
            if video:
                # Prepare output directory
                output_dir = os.path.join(os.getcwd(), "Downloads", self.current_anime.slug)
                os.makedirs(output_dir, exist_ok=True)

                # Initialize download control variables
                stop_event = threading.Event()
                self.download_controls[bolum.slug]['stop_event'] = stop_event

                # Start download in a separate thread
                download_thread = threading.Thread(
                    target=self.download_video,
                    args=(video, bolum, output_dir, stop_event),
                    daemon=True
                )
                download_thread.start()
                self.download_threads[bolum.slug] = download_thread
            else:
                messagebox.showerror("Hata", f"{bolum.title} indirilemedi.")

    def download_video(self, video, bolum, output_dir, stop_event):
        # Update progress bar
        def progress_hook(d):
            if stop_event.is_set():
                raise Exception("Download paused")
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded_bytes = d.get('downloaded_bytes', 0)
                if total_bytes:
                    progress = downloaded_bytes / total_bytes
                    self.progress_bars[bolum.slug].set(progress)

        try:
            video.indir(callback=progress_hook, output=output_dir)
            # Mark episode as downloaded
            self.dosyalar.set_gecmis(self.current_anime.slug, bolum.slug, "indirildi")
            # Update progress bar to 100%
            self.progress_bars[bolum.slug].set(1.0)
            # Change pause button to disabled
            self.download_controls[bolum.slug]['pause_button'].configure(state='disabled')
        except Exception as e:
            # Handle pause
            if str(e) == "Download paused":
                pass  # Do nothing, download is paused
            else:
                messagebox.showerror("Hata", f"{bolum.title} indirilemedi.")

    def pause_download(self, bolum):
        control = self.download_controls[bolum.slug]
        if control['paused']:
            # Resume download
            control['paused'] = False
            control['pause_button'].configure(text='Duraklat')
            # Create a new stop_event
            stop_event = threading.Event()
            control['stop_event'] = stop_event
            # Restart the download thread
            video = bolum.best_video()
            output_dir = os.path.join(os.getcwd(), "Downloads", self.current_anime.slug)
            download_thread = threading.Thread(
                target=self.download_video,
                args=(video, bolum, output_dir, stop_event),
                daemon=True
            )
            download_thread.start()
            self.download_threads[bolum.slug] = download_thread
        else:
            # Pause download
            control['paused'] = True
            control['pause_button'].configure(text='Devam Et')
            # Signal the download thread to stop
            control['stop_event'].set()

    def on_closing(self):
        # Stop all download threads
        for control in self.download_controls.values():
            if 'stop_event' in control:
                control['stop_event'].set()
        self.driver.quit()
        self.destroy()

if __name__ == "__main__":
    app = TurkanimeGUI()
    app.mainloop()
