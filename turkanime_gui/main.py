import customtkinter as ctk
from turkanime_api.objects import Anime
from turkanime_api.webdriver import create_webdriver
from dosyalar import Dosyalar
import threading
from tkinter import messagebox
import os
import subprocess  # Add this line

# Add these constants at the top after imports
PADDING = 10
CORNER_RADIUS = 8
BUTTON_COLOR = "#1f538d"
BUTTON_HOVER_COLOR = "#1a4572"
FRAME_COLOR = "#2b2b2b"
TEXT_COLOR = "#ffffff"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TurkanimeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Turkanime GUI")
        self.geometry("1000x800")  # Increased window size

        # Configure colors and styling
        self.configure(fg_color="#1a1a1a")  # Darker background

        self.dosyalar = Dosyalar()
        self.driver = create_webdriver()
        self.anime_list = Anime.get_anime_listesi(self.driver)
        self.current_anime = None
        self.selected_episodes = []
        self.download_threads = {}
        self.download_controls = {}
        self.is_playing_episode = False  # Flag to prevent multiple episodes playing

        self.items_per_page = 20  # Customizable count of anime displayed per page
        self.current_page = 0
        self.search_results = self.anime_list  # Initialize search results with full anime list

        # Create frames for different pages
        self.anime_list_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.anime_list_frame.grid(row=0, column=0, sticky="nsew")
        self.anime_list_frame.grid_rowconfigure(1, weight=1)
        self.anime_list_frame.grid_columnconfigure(0, weight=1)

        self.episode_list_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.episode_list_frame.grid(row=0, column=0, sticky="nsew")
        self.episode_list_frame.grid_rowconfigure(1, weight=1)
        self.episode_list_frame.grid_columnconfigure(0, weight=1)
        self.episode_list_frame.grid_remove()  # Hide episode list frame initially

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Show the anime list on launch
        self.update_search_results()

    def create_widgets(self):
        # Configure grid layout for the anime list frame
        # Search Frame styling
        self.search_frame = ctk.CTkFrame(self.anime_list_frame, fg_color=FRAME_COLOR, corner_radius=CORNER_RADIUS)
        self.search_frame.grid(row=0, column=0, sticky="ew", padx=PADDING, pady=PADDING)
        self.search_frame.grid_columnconfigure(1, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Anime adı girin",
            height=35,
            corner_radius=CORNER_RADIUS,
            border_width=2
        )
        self.search_entry.grid(row=0, column=1, padx=PADDING, pady=PADDING, sticky="ew")
        self.search_entry.bind("<Return>", lambda event: self.search_anime())
        self.search_entry.bind("<KeyRelease>", self.on_key_release)

        self.search_button = ctk.CTkButton(
            self.search_frame,
            text="Ara",
            height=35,
            corner_radius=CORNER_RADIUS,
            fg_color=BUTTON_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.search_anime
        )
        self.search_button.grid(row=0, column=2, padx=PADDING, pady=PADDING)

        # Results Frame styling - Update background color
        self.results_frame = ctk.CTkFrame(self.anime_list_frame, fg_color=FRAME_COLOR, corner_radius=CORNER_RADIUS)
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=PADDING, pady=(0, PADDING))
        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(0, weight=1)

        # Scrollable Canvas for Results - Update background and bind mouse wheel
        self.canvas = ctk.CTkCanvas(self.results_frame, bg=FRAME_COLOR, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Bind mouse wheel events to the canvas
        self.canvas.bind("<Enter>", lambda _: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows and macOS
        self.canvas.bind("<Button-4>", self._on_mousewheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mousewheel)    # Linux scroll down

        self.scrollbar = ctk.CTkScrollbar(self.results_frame, command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Update scrollable frame background
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color=FRAME_COLOR)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        # Update canvas window configuration
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=self.canvas.winfo_width())
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Pagination Controls styling
        self.pagination_frame = ctk.CTkFrame(self.anime_list_frame, fg_color=FRAME_COLOR, corner_radius=CORNER_RADIUS)
        self.pagination_frame.grid(row=2, column=0, pady=PADDING, padx=PADDING, sticky="ew")
        self.pagination_frame.grid_columnconfigure(1, weight=1)

        self.prev_button = ctk.CTkButton(
            self.pagination_frame,
            text="Önceki",
            height=35,
            corner_radius=CORNER_RADIUS,
            fg_color=BUTTON_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.prev_page
        )
        self.prev_button.grid(row=0, column=0, padx=PADDING, pady=PADDING)

        self.page_label = ctk.CTkLabel(self.pagination_frame, text=f"Sayfa {self.current_page + 1}")
        self.page_label.grid(row=0, column=1, padx=PADDING, pady=PADDING)

        self.next_button = ctk.CTkButton(
            self.pagination_frame,
            text="Sonraki",
            height=35,
            corner_radius=CORNER_RADIUS,
            fg_color=BUTTON_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.next_page
        )
        self.next_button.grid(row=0, column=2, padx=PADDING, pady=PADDING)

    def on_closing(self):
        # Stop all download threads
        for control in self.download_controls.values():
            if 'stop_event' in control:
                control['stop_event'].set()
        self.driver.quit()
        self.destroy()  

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

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if event.num == 5 or event.delta == -120 or event.delta == -1:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta == 120 or event.delta == 1:
            self.canvas.yview_scroll(-1, "units")
        elif event.delta:
            # For other platforms
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_configure(self, event):
        """Update the scroll region when the canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

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
        # Hide the anime list frame and show the episode list frame
        self.anime_list_frame.grid_remove()
        self.episode_list_frame.grid()

        self.current_anime = Anime(self.driver, slug)
        episodes = self.current_anime.bolumler
        self.selected_episodes = []
        self.download_threads = {}
        self.download_controls = {}

        # Clear any existing widgets in episode_list_frame
        for widget in self.episode_list_frame.winfo_children():
            widget.destroy()

        # Configure grid for episode_list_frame
        self.episode_list_frame.grid_rowconfigure(2, weight=1)
        self.episode_list_frame.grid_columnconfigure(0, weight=1)

        # Add Back Button
        self.back_button = ctk.CTkButton(
            self.episode_list_frame,
            text="Geri",
            height=35,
            corner_radius=CORNER_RADIUS,
            fg_color=BUTTON_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.back_to_anime_list
        )
        self.back_button.grid(row=0, column=0, sticky="w", padx=PADDING, pady=PADDING)

        # Add Episode Search Bar
        self.episode_search_entry = ctk.CTkEntry(
            self.episode_list_frame,
            width=400,
            height=35,
            placeholder_text="Bölüm adı ara",
            corner_radius=CORNER_RADIUS,
            border_width=2
        )
        self.episode_search_entry.grid(row=1, column=0, padx=PADDING, pady=(0, PADDING), sticky="ew")
        self.episode_search_entry.bind("<KeyRelease>", self.on_episode_search)

        # Scrollable frame for episodes
        self.episode_results_frame = ctk.CTkFrame(self.episode_list_frame, fg_color=FRAME_COLOR)
        self.episode_results_frame.grid(row=2, column=0, sticky="nsew", padx=PADDING, pady=(0, PADDING))
        self.episode_list_frame.grid_rowconfigure(2, weight=1)

        # Scrollable Canvas for Episodes
        self.episode_canvas = ctk.CTkCanvas(self.episode_results_frame, bg=FRAME_COLOR, highlightthickness=0)
        self.episode_canvas.grid(row=0, column=0, sticky="nsew")
        self.episode_results_frame.grid_rowconfigure(0, weight=1)
        self.episode_results_frame.grid_columnconfigure(0, weight=1)

        self.episode_scrollbar = ctk.CTkScrollbar(self.episode_results_frame, command=self.episode_canvas.yview)
        self.episode_scrollbar.grid(row=0, column=1, sticky="ns")
        self.episode_canvas.configure(yscrollcommand=self.episode_scrollbar.set)

        self.episode_scrollable_frame = ctk.CTkFrame(self.episode_canvas, fg_color=FRAME_COLOR)
        self.episode_canvas.create_window((0, 0), window=self.episode_scrollable_frame, anchor="nw")
        self.episode_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.episode_canvas.configure(
                scrollregion=self.episode_canvas.bbox("all")
            )
        )

        # Add Select All Episodes Checkbox
        self.select_all_var = ctk.BooleanVar()
        self.select_all_checkbox = ctk.CTkCheckBox(
            self.episode_scrollable_frame,
            text="Tüm Bölümleri Seç",
            height=30,
            corner_radius=CORNER_RADIUS,
            border_width=2,
            variable=self.select_all_var,
            command=self.on_select_all_episodes
        )
        self.select_all_checkbox.pack(pady=PADDING)

        # Style the download button
        self.download_button = ctk.CTkButton(
            self.episode_scrollable_frame,
            text="Seçili Bölümleri İndir",
            height=40,
            corner_radius=CORNER_RADIUS,
            fg_color=BUTTON_COLOR,
            hover_color=BUTTON_HOVER_COLOR,
            command=self.download_selected_episodes
        )
        self.download_button.pack(pady=PADDING)

        watched_episodes = self.dosyalar.get_gecmis(self.current_anime.slug, "izlendi")
        downloaded_episodes = self.dosyalar.get_gecmis(self.current_anime.slug, "indirildi")

        # Episode Checkboxes
        self.episode_vars = []
        self.episode_frames = []
        for bolum in episodes:
            episode_frame = ctk.CTkFrame(
                self.episode_scrollable_frame,
                fg_color=FRAME_COLOR,
                corner_radius=CORNER_RADIUS
            )
            episode_frame.pack(fill="x", pady=5, padx=PADDING)
            episode_frame.grid_columnconfigure(1, weight=1)

            episode_title = bolum.title

            # Indicate watched and downloaded episodes
            indicators = ""
            if bolum.slug in watched_episodes:
                indicators += "👁"
            if bolum.slug in downloaded_episodes:
                indicators += "⤓"

            display_title = f"{indicators} {episode_title}"

            var = ctk.BooleanVar()
            episode_checkbox = ctk.CTkCheckBox(
                episode_frame,
                text=display_title,
                variable=var,
                command=lambda b=bolum, v=var: self.on_episode_select(b, v)
            )
            episode_checkbox.grid(row=0, column=0, sticky="w", padx=PADDING, pady=PADDING)
            self.episode_vars.append(var)
            self.episode_frames.append((episode_frame, bolum, var))

            # Play Button
            play_button = ctk.CTkButton(
                episode_frame,
                text="Oynat",
                width=80,
                height=32,
                corner_radius=CORNER_RADIUS,
                fg_color=BUTTON_COLOR,
                hover_color=BUTTON_HOVER_COLOR,
                command=lambda b=bolum: self.play_episode(b)
            )
            play_button.grid(row=0, column=1, sticky="e", padx=PADDING, pady=PADDING)

    def back_to_anime_list(self):
        # Hide the episode list frame and show the anime list frame
        self.episode_list_frame.grid_remove()
        self.anime_list_frame.grid()

    def on_episode_search(self, event):
        query = self.episode_search_entry.get().lower()
        for episode_frame, bolum, var in self.episode_frames:
            if query in bolum.title.lower():
                episode_frame.pack(fill="x", pady=2)
            else:
                episode_frame.pack_forget()

    def on_select_all_episodes(self):
        select_all = self.select_all_var.get()
        for episode_frame, bolum, var in self.episode_frames:
            var.set(select_all)
            if select_all:
                if bolum not in self.selected_episodes:
                    self.selected_episodes.append(bolum)
            else:
                if bolum in self.selected_episodes:
                    self.selected_episodes.remove(bolum)

    def on_episode_select(self, bolum, var):
        if var.get():
            if bolum not in self.selected_episodes:
                self.selected_episodes.append(bolum)
        else:
            if bolum in self.selected_episodes:
                self.selected_episodes.remove(bolum)
        # Update select all checkbox state
        if all(var.get() for _, _, var in self.episode_frames):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)

    def play_episode(self, bolum):
        if self.is_playing_episode:
            messagebox.showwarning("Uyarı", "Zaten bir bölüm oynatılıyor.")
            return
        self.is_playing_episode = True

        # Show loading animation
        self.loading_window = ctk.CTkToplevel(self)
        self.loading_window.title("Yükleniyor...")
        self.loading_window.geometry("300x100")
        self.loading_window.resizable(False, False)
        self.loading_window.grab_set()  # Make it modal

        loading_label = ctk.CTkLabel(self.loading_window, text="Bölüm yükleniyor, lütfen bekleyin...")
        loading_label.pack(pady=10)

        self.loading_progress = ctk.CTkProgressBar(self.loading_window)
        self.loading_progress.set(0)
        self.loading_progress.pack(pady=10, padx=20, fill="x")
        self.loading_progress.start()  # Start indeterminate mode

        threading.Thread(target=self._play_video, args=(bolum,), daemon=True).start()

    def _play_video(self, bolum):
        try:
            video = bolum.best_video()
            if video:
                # Get the video URL
                video_url = video.url

                # Start mpv using subprocess.Popen without '--no-terminal'
                mpv_command = ['mpv', video_url]

                mpv_process = subprocess.Popen(
                    mpv_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line buffering
                    encoding='utf-8',  # Specify encoding
                    errors='replace'  # Handle decoding errors
                )

                # Read mpv output line by line
                for line in iter(mpv_process.stdout.readline, ''):
                    print(f"mpv output: {line.strip()}")  # Debug output
                    if "VO:" in line or "AO:" in line:
                        # Playback has started
                        # Close loading animation
                        self.after(0, self.close_loading_animation)
                        break

                # Wait for mpv process to finish
                mpv_process.wait()

                # Video playback finished
                self.is_playing_episode = False

                # Mark episode as watched
                self.dosyalar.set_gecmis(self.current_anime.slug, bolum.slug, "izlendi")

                # Update the episode list on the main thread
                self.after(0, self.show_episodes, self.current_anime.slug)
            else:
                self.is_playing_episode = False
                self.after(0, self.close_loading_animation)
                messagebox.showerror("Hata", f"{bolum.title} oynatılamadı.")
        except Exception as e:
            self.is_playing_episode = False
            self.after(0, self.close_loading_animation)
            messagebox.showerror("Hata", f"{bolum.title} oynatılırken bir hata oluştu.\n{str(e)}")

    def close_loading_animation(self):
        if hasattr(self, 'loading_window') and self.loading_window.winfo_exists():
            self.loading_progress.stop()
            self.loading_window.grab_release()
            self.loading_window.destroy()

    def download_selected_episodes(self):
        if not self.selected_episodes:
            messagebox.showwarning("Uyarı", "Lütfen indirilecek bölümleri seçin.")
            return

        # Style the progress window
        self.progress_window = ctk.CTkToplevel(self)
        self.progress_window.title("İndirme Durumu")
        self.progress_window.geometry("600x500")
        self.progress_window.configure(fg_color="#1a1a1a")

        # Scrollable frame for progress bars
        self.progress_canvas = ctk.CTkCanvas(self.progress_window)
        self.progress_canvas.grid(row=0, column=0, sticky="nsew")
        self.progress_scrollbar = ctk.CTkScrollbar(self.progress_window, command=self.progress_canvas.yview)
        self.progress_scrollbar.grid(row=0, column=1, sticky="ns")
        self.progress_canvas.configure(yscrollcommand=self.progress_scrollbar.set)

        self.progress_frame = ctk.CTkFrame(self.progress_canvas)
        self.progress_canvas.create_window((0, 0), window=self.progress_frame, anchor="nw")

        self.progress_frame.bind(
            "<Configure>",
            lambda e: self.progress_canvas.configure(
                scrollregion=self.progress_canvas.bbox("all")
            )
        )

        self.progress_bars = {}
        for bolum in self.selected_episodes:
            frame = ctk.CTkFrame(self.progress_frame)
            frame.pack(fill="x", pady=5)
            frame.grid_columnconfigure(1, weight=1)

            label = ctk.CTkLabel(frame, text=bolum.title)
            label.grid(row=0, column=0, padx=5, sticky="w")

            progress = ctk.CTkProgressBar(frame)
            progress.set(0)
            progress.grid(row=0, column=1, padx=5, sticky="ew")
            self.progress_bars[bolum.slug] = progress

            pause_button = ctk.CTkButton(frame, text="Duraklat", width=70,
                                         command=lambda b=bolum: self.pause_download(b))
            pause_button.grid(row=0, column=2, padx=5)
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
            # Refresh episode list
            self.after(0, self.show_episodes, self.current_anime.slug)
        except Exception as e:
            # Handle pause
            if str(e) == "Download paused":
                pass  # Do nothing, download is paused
            else:
                messagebox.showerror("Hata", f"{bolum.title} indirilemedi.\n{str(e)}")

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

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_canvas_configure(self, event):
        """Update the scroll region when the canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

if __name__ == "__main__":
    app = TurkanimeGUI()
    app.mainloop()
