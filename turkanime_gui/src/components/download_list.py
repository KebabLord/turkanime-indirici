import customtkinter as ctk
from turkanime_api.objects import Anime
import threading

class DownloadList(ctk.CTkFrame):
    def __init__(self, master, driver, anime_slug, app=None):
        super().__init__(master)
        self.driver = driver
        self.app = app
        self.anime_slug = anime_slug
        self.anime = None
        self.selected_episodes = set()
        
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Setup UI components
        self.setup_ui()
        
        # Load episodes in background
        self.load_episodes()
    
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
        
        # Download selected button
        self.download_button = ctk.CTkButton(
            self.header_frame,
            text="Seçilenleri İndir",
            width=120,
            state="disabled",
            command=self.download_selected
        )
        self.download_button.pack(side="right", padx=10, pady=10)
        
        # Select all checkbox
        self.select_all_var = ctk.BooleanVar()
        self.select_all_checkbox = ctk.CTkCheckBox(
            self.header_frame,
            text="Tümünü Seç",
            variable=self.select_all_var,
            command=self.toggle_all
        )
        self.select_all_checkbox.pack(side="right", padx=10, pady=10)
        
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
            print(f"Loading anime for download: {self.anime_slug}")
            
            # Create anime object using API
            self.anime = Anime(self.driver, self.anime_slug)
            
            # Update UI in main thread
            self.after(0, lambda: self.title_label.configure(text=self.anime.title))
            
            # Get episodes using API's bolumler property
            if not hasattr(self.anime, 'bolumler'):
                raise ValueError("No episodes property found for this anime")
            
            episodes = self.anime.bolumler
            if not episodes:  # Check if episodes list is empty
                raise ValueError("No episodes found for this anime")
            
            print(f"Found {len(episodes)} episodes")
            
            # Update UI in main thread
            self.after(0, lambda: self.display_episodes(episodes))
            
        except Exception as error:
            print(f"Error loading episodes: {type(error).__name__} - {str(error)}")
            # Show error in UI
            error_msg = f"Bölümler yüklenemedi:\n{str(error)}"
            self.after(0, lambda: self.show_error(error_msg))
    
    def display_episodes(self, episodes):
        # Clear loading message
        self.loading_label.destroy()
        
        # Display episodes in chronological order
        for episode in episodes:
            episode_frame = ctk.CTkFrame(self.scrollable_frame)
            episode_frame.pack(fill="x", padx=5, pady=2)
            
            # Checkbox for episode selection
            checkbox_var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(
                episode_frame,
                text="",
                variable=checkbox_var,
                command=lambda ep=episode, var=checkbox_var: self.toggle_episode(ep, var)
            )
            checkbox.pack(side="left", padx=5)
            
            # Episode title
            title_label = ctk.CTkLabel(
                episode_frame,
                text=episode.title,
                anchor="w"
            )
            title_label.pack(side="left", padx=5, pady=5, fill="x", expand=True)
    
    def toggle_episode(self, episode, checkbox_var):
        if checkbox_var.get():
            self.selected_episodes.add(episode)
        else:
            self.selected_episodes.discard(episode)
        
        # Enable/disable download button based on selection
        self.download_button.configure(
            state="normal" if self.selected_episodes else "disabled"
        )
    
    def toggle_all(self):
        is_selected = self.select_all_var.get()
        
        # Update all checkboxes
        for child in self.scrollable_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                checkbox = child.winfo_children()[0]
                checkbox.select() if is_selected else checkbox.deselect()
        
        # Update selected episodes
        if is_selected:
            self.selected_episodes = set(self.anime.bolumler)
        else:
            self.selected_episodes.clear()
        
        # Update download button state
        self.download_button.configure(
            state="normal" if self.selected_episodes else "disabled"
        )
    
    def download_selected(self):
        # TODO: Implement download functionality using DownloadManager
        print(f"Selected episodes for download: {len(self.selected_episodes)}")
        for episode in self.selected_episodes:
            print(f"- {episode.title}")
    
    def show_error(self, error_message):
        error_window = ctk.CTkToplevel(self)
        error_window.title("Hata")
        error_window.geometry("400x150")
        
        error_label = ctk.CTkLabel(
            error_window,
            text=f"Bölümler yüklenemedi:\n{error_message}",
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
        self.app.show_downloads()