import threading
import customtkinter as ctk
from turkanime_api.objects import Anime
import shutil
import subprocess
import sys
import webbrowser
import os
from turkanime_gui.src.components.download_manager import DownloadManager

class EpisodeList(ctk.CTkFrame):
    def __init__(self, master, driver, anime_slug, app=None):
        super().__init__(master)
        self.driver = driver
        self.app = app
        self.anime_slug = anime_slug
        self.anime = None
        self.dosyalar = app.dosyalar  # Get reference to Dosyalar instance
        
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Setup UI components
        self.setup_ui()
        
        # Load episodes in background
        threading.Thread(target=self.load_episodes, daemon=True).start()
    
    def setup_ui(self):
        # Header frame
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        
        # Back button
        self.back_button = ctk.CTkButton(
            self.header_frame,
            text="← Geri",
            width=70,
            command=self.go_back
        )
        self.back_button.pack(side="left", padx=10, pady=10)
        
        # Anime title
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="Yükleniyor...",
            font=("Arial", 16, "bold")
        )
        self.title_label.pack(side="left", padx=10, pady=10)
        
        # Scrollable episode list
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Initial loading message
        self.loading_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Bölümler yükleniyor...",
            font=("Arial", 14)
        )
        self.loading_label.pack(pady=20)
    
    def load_episodes(self):
        try:
            print(f"Loading anime: {self.anime_slug}")
            
            # Create anime object using API and fetch info
            self.anime = Anime(self.driver, self.anime_slug)
            self.anime.fetch_info()
            
            # Update UI in main thread with anime title
            self.after(0, lambda: self.title_label.configure(text=self.anime.title))
            
            # Get episodes using API's bolumler property
            episodes = self.anime.bolumler
            if not episodes:
                raise ValueError("No episodes found for this anime")
            
            print(f"Found {len(episodes)} episodes")
            
            # Update UI in main thread
            self.after(0, lambda: self.display_episodes(episodes))
            
        except Exception as error:
            print(f"Error loading episodes: {type(error).__name__} - {str(error)}")
            error_msg = f"Bölümler yüklenemedi:\n{str(error)}"
            self.after(0, lambda: self.show_error(error_msg))
    
    def display_episodes(self, episodes):
        """Display episode list in UI"""
        for episode in episodes:
            # Create episode button
            button = ctk.CTkButton(
                self.scrollable_frame,
                text=f"{episode.title}",
                command=lambda e=episode: self.on_episode_select(e)
            )
            button.pack(pady=2, padx=5, fill="x")
    
    def on_episode_select(self, episode):
        """Handle episode selection"""
        try:
            # Get the best video for this episode
            video = episode.best_video(by_res=True)
            if not video or not video.is_working:
                raise ValueError("No working video found for this episode")
                
            # Play or handle the video as needed
            video.oynat()
            
        except Exception as e:
            print(f"Error playing episode: {type(e).__name__} - {str(e)}")
            self.show_error(f"Bölüm oynatılamadı:\n{str(e)}")
    
    def download_episode(self, episode):
        # Create download window
        download_window = ctk.CTkToplevel(self)
        download_window.title(f"İndirme: {episode.title}")
        download_window.geometry("600x400")
        
        # Create and show download manager
        download_manager = DownloadManager(
            download_window,
            episode,
            app=self.app
        )
        download_manager.pack(expand=True, fill="both", padx=20, pady=20)
    
    def watch_episode(self, episode):
        # Show loading dialog
        loading_window = ctk.CTkToplevel(self)
        loading_window.title("Yükleniyor")
        loading_window.geometry("300x100")
        
        loading_label = ctk.CTkLabel(
            loading_window,
            text=f"Video kaynağı aranıyor...\n{episode.title}"
        )
        loading_label.pack(pady=20)
        
        # Mark episode as watched
        self.dosyalar.izlenen_ekle(self.anime_slug, episode.slug)
        
        # Refresh the episode list to update watched status
        self.after(0, lambda: self.refresh_episode_status(episode.slug))
        
        # Start video loading in background
        threading.Thread(
            target=self.load_and_play_video,
            args=(episode, loading_window),
            daemon=True
        ).start()
    
    def refresh_episode_status(self, watched_slug):
        """Refresh the visual status of episodes after watching one"""
        watched_episodes = self.dosyalar.izlenenler.get(self.anime_slug, [])
        
        # Update all episode frames
        for child in self.scrollable_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                # Get the title label and status indicator
                status_indicator = child.winfo_children()[0]
                title_label = child.winfo_children()[1]
                
                # Extract episode slug from title (you'll need to implement this)
                episode_slug = self.get_episode_slug_from_title(title_label.cget("text"))
                
                # Update status
                if episode_slug in watched_episodes:
                    status_indicator.configure(text="✓")
                    title_label.configure(text_color="gray60")
                else:
                    status_indicator.configure(text="")
                    title_label.configure(text_color="white")
    
    def get_episode_slug_from_title(self, title):
        """Helper method to get episode slug from displayed title"""
        # Find the episode with matching title
        for episode in self.anime.bolumler:
            if episode.title == title:
                return episode.slug
        return None
    
    def check_mpv_installed(self):
        """Check if MPV is installed and accessible"""
        # First check PATH
        if shutil.which('mpv') is not None:
            return True
            
        # Check common installation locations
        common_paths = [
            "C:\\Program Files\\mpv\\mpv.exe",
            "C:\\Program Files (x86)\\mpv\\mpv.exe",
            os.path.expanduser("~\\AppData\\Local\\Programs\\mpv\\mpv.exe"),
            os.path.expanduser("~\\scoop\\apps\\mpv\\current\\mpv.exe")
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                # Found MPV, add its directory to PATH
                mpv_dir = os.path.dirname(path)
                os.environ["PATH"] = mpv_dir + os.pathsep + os.environ["PATH"]
                return True
                
        return False
    
    def show_mpv_install_guide(self):
        """Show MPV installation instructions"""
        guide_window = ctk.CTkToplevel(self)
        guide_window.title("MPV Kurulumu")
        guide_window.geometry("500x300")
        
        text = """MPV Player kurulu değil veya PATH'e eklenmemiş.

Windows için kurulum adımları:
1. https://sourceforge.net/projects/mpv-player-windows/files/latest/download adresinden MPV'yi indirin
2. İndirilen zip dosyasının içeriklerini C:/Program Files klasöründe mpv klasörü açıp içine kopyalayın.
3. updater.bat dosyasını yönetici olarak çalıştırarak MPV dosyalarını indirin.
4. Sonrasında installer klasörünün içerisindeki mpv-install.bat dosyasını yönetici olarak çalıştırarak MPV kurulumunu tamamlayın.
5. Bu konumu sistem PATH'ine ekleyin:
   - Sistem Özellikleri > Gelişmiş > Ortam Değişkenleri
   - Path değişkenini düzenleyin
   - "C:/Program Files/mpv" ekleyin

Kurulum tamamlandıktan sonra uygulamayı yeniden başlatın."""
        
        guide_label = ctk.CTkLabel(
            guide_window,
            text=text,
            justify="left",
            wraplength=450
        )
        guide_label.pack(pady=20, padx=20)
        
        download_btn = ctk.CTkButton(
            guide_window,
            text="MPV İndir",
            command=lambda: webbrowser.open('https://sourceforge.net/projects/mpv-player-windows/files/latest/download')
        )
        download_btn.pack(pady=10)
        
        ok_btn = ctk.CTkButton(
            guide_window,
            text="Tamam",
            command=guide_window.destroy
        )
        ok_btn.pack(pady=10)
    
    def load_and_play_video(self, episode, loading_window):
        try:
            print(f"Finding best video source for: {episode.title}")
            video = episode.best_video()
            
            if video is None:
                raise Exception("Kullanılabilir video kaynağı bulunamadı")
            
            # Close loading window in main thread
            self.after(0, loading_window.destroy)
            
            print(f"Playing video using {video.player} player")
            print(f"Video URL: {video.url}")
            
            # Try to find MPV executable
            mpv_paths = [
                "C:\\Program Files\\mpv\\mpv.exe",
                "C:\\Program Files (x86)\\mpv\\mpv.exe",
                os.path.expanduser("~\\AppData\\Local\\Programs\\mpv\\mpv.exe"),
                os.path.expanduser("~\\scoop\\apps\\mpv\\current\\mpv.exe")
            ]
            
            mpv_exe = None
            for path in mpv_paths:
                if os.path.isfile(path):
                    mpv_exe = path
                    break
                    
            if mpv_exe is None:
                raise Exception("MPV bulunamadı. Lütfen MPV'yi yükleyin ve PATH'e ekleyin.")
            
            print(f"Using MPV from: {mpv_exe}")
            
            # Create command list
            cmd = [
                mpv_exe,
                "--force-window=yes",
                "--ontop",
                "--focus-on=open",
                "--msg-level=all=v",
                video.url
            ]
            
            # Run MPV with subprocess
            result = subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if result.returncode != 0:
                print(f"MPV Return Code: {result.returncode}")
                print(f"MPV STDOUT: {result.stdout}")
                print(f"MPV STDERR: {result.stderr}")
                raise Exception(f"MPV Hatası:\nReturn Code: {result.returncode}\nError: {result.stderr}")
                
        except Exception as e:
            error_msg = str(e)
            print(f"Detailed error: {error_msg}")
            self.after(0, loading_window.destroy)
            self.after(0, lambda error=error_msg: self.show_error(error))
    
    def show_error(self, error_message):
        error_window = ctk.CTkToplevel(self)
        error_window.title("Hata")
        error_window.geometry("400x150")
        
        error_label = ctk.CTkLabel(
            error_window,
            text=f"Video oynatılamadı:\n{error_message}",
            text_color="red"
        )
        error_label.pack(pady=20)
        
        ok_button = ctk.CTkButton(
            error_window,
            text="Tamam",
            command=error_window.destroy
        )
        ok_button.pack(pady=10)
    
    def go_back(self):
        self.app.show_anime_list()