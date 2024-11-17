import sys
from pathlib import Path
import threading
from queue import Queue
from customtkinter import CTkProgressBar

# Add project root to Python path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

from turkanime_api.webdriver import create_webdriver, elementi_bekle
from turkanime_api.cli.dosyalar import Dosyalar
import customtkinter as ctk
import atexit
from components.anime_list import AnimeList
from components.episode_list import EpisodeList
from components.download_list import DownloadList
from turkanime_api.objects import Anime

def log_status(message):
    """Helper function to log status to console"""
    print(f"Status: {message}")

class LoadingOverlay(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.configure(fg_color=("gray85", "gray10"))
        
        # Center the loading content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create center frame for loading elements
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=0, column=0)
        
        # Loading spinner
        self.spinner = CTkProgressBar(center_frame, mode="indeterminate")
        self.spinner.grid(row=0, column=0, padx=20, pady=(20,10))
        self.spinner.start()
        
        # Status text
        self.status_label = ctk.CTkLabel(
            center_frame, 
            text="TürkAnime'ye bağlanılıyor...",
            font=("Arial", 14)
        )
        self.status_label.grid(row=1, column=0, padx=20, pady=(0,20))
    
    def update_status(self, text):
        self.status_label.configure(text=text)
        log_status(text)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("TürkAnimu")
        self.geometry("1100x700")
        
        # Initialize queue for thread communication
        self.queue = Queue()
        
        # Initialize driver and load anime list in background
        self.driver = None
        self.anime_list_data = None
        
        # Initialize dosyalar
        self.dosyalar = Dosyalar()
        
        # Initialize with default settings if needed
        default_ayarlar = {
            "manuel fansub": False,
            "izlerken kaydet": False,
            "indirilenler": ".",
            "izlendi ikonu": True,
            "paralel indirme sayisi": 3,
            "max resolution": True,
            "dakika hatirla": True,
            "aria2c kullan": False
        }
        self.dosyalar.set_ayar(ayar_list=default_ayarlar)
        
        # Configure grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Create sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # Create main content area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.setup_sidebar()
        
        # Show loading overlay
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Initialize background tasks
        self.initialize_background()
        
        # Start checking queue
        self.check_queue()
    
    def initialize_background(self):
        def background_task():
            try:
                # Initialize driver
                self.queue.put(("status_update", "Firefox başlatılıyor..."))
                self.driver = create_webdriver(preload_ta=False)
                
                # Connect to turkanime
                self.queue.put(("status_update", "TürkAnime'ye bağlanılıyor..."))
                self.driver.get("https://turkanime.co/kullanici/anonim")
                elementi_bekle(".navbar-nav", self.driver)
                
                # Get anime list
                self.queue.put(("status_update", "Anime listesi yükleniyor..."))
                from turkanime_api.objects import Anime
                self.anime_list_data = Anime.get_anime_listesi(self.driver)
                
                # Signal completion
                self.queue.put(("init_complete", None))
                log_status("Initialization complete!")
            except Exception as e:
                self.queue.put(("init_error", str(e)))
                log_status(f"Error: {str(e)}")
        
        # Start background thread
        thread = threading.Thread(target=background_task)
        thread.daemon = True
        thread.start()
    
    def check_queue(self):
        try:
            msg_type, data = self.queue.get_nowait()
            
            if msg_type == "status_update":
                self.loading_overlay.update_status(data)
            elif msg_type == "init_complete":
                # Enable buttons
                self.anime_button.configure(state="normal")
                self.download_button.configure(state="normal")
                # Remove loading overlay
                self.loading_overlay.place_forget()
            elif msg_type == "init_error":
                # Update loading overlay to show error
                self.loading_overlay.update_status(f"Hata: {data}")
                self.loading_overlay.spinner.stop()
                
        except:
            pass
        finally:
            # Check queue again after 100ms
            self.after(100, self.check_queue)
    
    def setup_sidebar(self):
        # Logo/title
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TürkAnimu", font=("Arial", 20))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Navigation buttons - disabled until initialization complete
        self.anime_button = ctk.CTkButton(
            self.sidebar_frame, 
            text="Anime İzle", 
            command=self.show_anime_list,
            state="disabled"
        )
        self.anime_button.grid(row=1, column=0, padx=20, pady=10)
        
        self.download_button = ctk.CTkButton(
            self.sidebar_frame, 
            text="Anime İndir", 
            command=self.show_downloads,
            state="disabled"
        )
        self.download_button.grid(row=2, column=0, padx=20, pady=10)
        
        self.settings_button = ctk.CTkButton(self.sidebar_frame, text="Ayarlar", command=self.show_settings)
        self.settings_button.grid(row=3, column=0, padx=20, pady=10)
    
    def show_anime_list(self):
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create and show anime list with reference to app
        anime_list = AnimeList(self.main_frame, self.driver, self.anime_list_data, app=self)  # Pass self as app
        anime_list.pack(fill="both", expand=True)
    
    def show_downloads(self):
        """Show download interface"""
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create and show anime list with download mode
        anime_list = AnimeList(
            self.main_frame, 
            self.driver, 
            self.anime_list_data, 
            app=self,
            mode="download"  # Add mode parameter to indicate download view
        )
        anime_list.pack(fill="both", expand=True)
    
    def show_download_episodes(self, anime_slug):
        """Show episode list for downloading"""
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create and show download list
        download_list = DownloadList(
            self.main_frame, 
            self.driver, 
            anime_slug,
            app=self
        )
        download_list.pack(expand=True, fill="both")
    
    def show_settings(self):
        # TODO: Implement settings view
        pass
    
    def show_episode_list(self, anime_slug):
        """Show episode list for selected anime"""
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create and show episode list
        episode_list = EpisodeList(
            self.main_frame, 
            self.driver, 
            anime_slug,
            app=self
        )
        episode_list.pack(expand=True, fill="both")
    
    def cleanup(self):
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def get_episode_list(self, anime_slug):
        """Get episode list for an anime using TurkAnime API"""
        try:
            print(f"Fetching episodes for: {anime_slug}")
            
            # Validate anime slug - it shouldn't start with underscore
            if anime_slug.startswith('_'):
                raise ValueError(f"Invalid anime slug: {anime_slug}")
            
            # Create anime object using API
            anime = Anime(self.driver, anime_slug)
            
            # Fetch anime info first
            anime.fetch_info()
            
            if not hasattr(anime, 'anime_id') or not anime.anime_id:
                raise ValueError(f"Could not fetch anime info for: {anime_slug}")
            
            print(f"Anime title: {anime.title}")
            print(f"Anime ID: {anime.anime_id}")
            
            # Get episodes using API's bolumler property
            episodes = anime.bolumler
            if not episodes:
                raise ValueError("No episodes found for this anime")
            
            print(f"Found {len(episodes)} episodes")
            return episodes
            
        except Exception as e:
            print(f"Error getting episode list: {type(e).__name__} - {str(e)}")
            print(f"Anime slug: {anime_slug}")
            raise
