import customtkinter as ctk
from queue import Queue
import threading
import os
from pathlib import Path

class DownloadManager(ctk.CTkFrame):
    def __init__(self, master, episodes, app=None):
        """
        Initialize download manager
        
        Args:
            episodes: List of Episode objects to download
            app: Reference to main app
        """
        super().__init__(master)
        self.episodes = episodes
        self.app = app
        self.download_queue = Queue()
        self.current_downloads = {}  # Track active downloads
        self.is_downloading = False
        
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header frame
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=f"İndirme Yöneticisi ({len(self.episodes)} bölüm)",
            font=("Arial", 16, "bold")
        )
        self.title_label.pack(side="left", padx=10, pady=10)
        
        # Download settings frame
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Fansub selection
        self.fansub_label = ctk.CTkLabel(
            self.settings_frame,
            text="Tercih edilen Fansub:",
            anchor="w"
        )
        self.fansub_label.pack(fill="x", padx=10, pady=(10,0))
        
        # Get unique fansubs from all episodes
        all_fansubs = set()
        for episode in self.episodes:
            all_fansubs.update(episode.fansubs)
        
        self.fansub_var = ctk.StringVar(value="En iyi kalite")
        self.fansub_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=["En iyi kalite"] + sorted(list(all_fansubs)),
            variable=self.fansub_var
        )
        self.fansub_menu.pack(fill="x", padx=10, pady=5)
        
        # Download progress frame
        self.progress_frame = ctk.CTkFrame(self.settings_frame)
        self.progress_frame.pack(fill="x", padx=10, pady=10)
        
        # Start/Stop button
        self.download_btn = ctk.CTkButton(
            self.settings_frame,
            text="İndirmeyi Başlat",
            command=self.toggle_download
        )
        self.download_btn.pack(pady=10)
    
    def create_progress_widget(self, episode):
        """Create progress widget for an episode"""
        frame = ctk.CTkFrame(self.progress_frame)
        frame.pack(fill="x", padx=5, pady=2)
        
        # Episode title
        title_label = ctk.CTkLabel(
            frame,
            text=episode.title,
            anchor="w"
        )
        title_label.pack(side="left", padx=5)
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(frame)
        progress_bar.pack(side="left", padx=5, fill="x", expand=True)
        progress_bar.set(0)
        
        # Status label
        status_label = ctk.CTkLabel(
            frame,
            text="Bekliyor...",
            width=100,
            anchor="w"
        )
        status_label.pack(side="right", padx=5)
        
        return {
            'frame': frame,
            'progress': progress_bar,
            'status': status_label
        }
    
    def toggle_download(self):
        if not self.is_downloading:
            self.start_downloads()
        else:
            self.stop_downloads()
    
    def start_downloads(self):
        self.is_downloading = True
        self.download_btn.configure(text="İndirmeyi Durdur", fg_color="red")
        
        # Create progress widgets for each episode
        for episode in self.episodes:
            if episode not in self.current_downloads:
                self.current_downloads[episode] = self.create_progress_widget(episode)
        
        # Start download thread
        threading.Thread(target=self.download_episodes, daemon=True).start()
    
    def stop_downloads(self):
        self.is_downloading = False
        self.download_btn.configure(text="İndirmeyi Başlat", fg_color=("blue", "darkblue"))
    
    def download_episodes(self):
        """Download all episodes"""
        selected_fansub = None if self.fansub_var.get() == "En iyi kalite" else self.fansub_var.get()
        
        for episode in self.episodes:
            if not self.is_downloading:
                break
                
            widgets = self.current_downloads[episode]
            
            try:
                # Get best video for selected fansub
                video = episode.best_video(by_fansub=selected_fansub)
                
                if video is None:
                    widgets['status'].configure(text="Video bulunamadı")
                    continue
                
                def progress_hook(d):
                    if not self.is_downloading:
                        return
                    
                    if d['status'] == 'downloading':
                        # Update progress
                        if 'total_bytes' in d:
                            progress = d['downloaded_bytes'] / d['total_bytes']
                            self.after(0, lambda: widgets['progress'].set(progress))
                        
                        # Update status
                        if 'speed' in d and d['speed'] is not None:
                            speed = d['speed'] / 1024 / 1024  # Convert to MB/s
                            self.after(0, lambda: widgets['status'].configure(
                                text=f"{speed:.1f} MB/s"
                            ))
                    
                    elif d['status'] == 'finished':
                        self.after(0, lambda: widgets['status'].configure(text="Tamamlandı"))
                        self.after(0, lambda: widgets['progress'].set(1))
                
                # Start download with progress callback
                widgets['status'].configure(text="İndiriliyor...")
                video.indir(callback=progress_hook)
                
            except Exception as e:
                widgets['status'].configure(text="Hata!")
                self.show_error(f"İndirme başarısız: {str(e)}")
    
    def show_error(self, error_message):
        error_window = ctk.CTkToplevel(self)
        error_window.title("Hata")
        error_window.geometry("400x150")
        
        error_label = ctk.CTkLabel(
            error_window,
            text=error_message,
            text_color="red"
        )
        error_label.pack(pady=20)
        
        ok_button = ctk.CTkButton(
            error_window,
            text="Tamam",
            command=error_window.destroy
        )
        ok_button.pack(pady=10)