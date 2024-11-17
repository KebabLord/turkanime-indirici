import customtkinter as ctk
from turkanime_api.objects import Anime
from turkanime_api.webdriver import elementi_bekle
from typing import List, Optional
import sys

class AnimeList(ctk.CTkFrame):
    def __init__(self, master, driver, anime_list_data, app=None, mode="watch"):
        super().__init__(master)
        self.driver = driver
        self.app = app
        self.mode = mode
        self.anime_list_data = anime_list_data
        self.filtered_anime = []
        
        # Initialize pagination variables
        self.current_page = 1
        self.items_per_page = 20
        
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.setup_ui()
        self.filter_anime("")  # Initialize filtered list
        self.display_current_page()
    
    def setup_ui(self):
        # Search frame
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        
        # Search entry
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *args: self.on_search_change())
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Anime ara...",
            textvariable=self.search_var
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        # Scrollable frame for anime list
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Navigation frame
        self.nav_frame = ctk.CTkFrame(self)
        self.nav_frame.grid(row=2, column=0, padx=10, pady=(0,10), sticky="ew")
        
        # Previous page button
        self.prev_btn = ctk.CTkButton(
            self.nav_frame,
            text="←",
            width=30,
            command=self.prev_page
        )
        self.prev_btn.pack(side="left", padx=5)
        
        # Page label
        self.page_label = ctk.CTkLabel(self.nav_frame, text="Sayfa 1")
        self.page_label.pack(side="left", padx=5)
        
        # Next page button
        self.next_btn = ctk.CTkButton(
            self.nav_frame,
            text="→",
            width=30,
            command=self.next_page
        )
        self.next_btn.pack(side="left", padx=5)
    
    def filter_anime(self, search_term: str):
        """Filter anime list based on search term"""
        search_term = search_term.lower()
        self.filtered_anime = [
            anime for anime in self.anime_list_data
            if search_term in anime[0].lower()
        ]
        self.current_page = 1  # Reset to first page when filtering
        self.update_navigation()
    
    def display_current_page(self):
        """Display current page of anime list"""
        # Clear current list
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Calculate slice indices
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        # Display anime entries for current page
        for anime_data in self.filtered_anime[start_idx:end_idx]:
            anime_frame = ctk.CTkFrame(self.scrollable_frame)
            anime_frame.pack(fill="x", padx=5, pady=2)
            
            # Anime title (anime_data[0] is title)
            title_label = ctk.CTkLabel(
                anime_frame,
                text=anime_data[0],
                anchor="w"
            )
            title_label.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            
            # Select button (anime_data[1] is URL)
            select_btn = ctk.CTkButton(
                anime_frame,
                text="Seç",
                width=70,
                command=lambda slug=anime_data[1].split('/')[-1]: self.on_anime_select(slug)
            )
            select_btn.pack(side="right", padx=10, pady=5)
        
        # Update navigation
        self.update_navigation()
    
    def get_slug_from_url(self, url):
        """Extract slug from anime URL"""
        # Remove any leading/trailing slashes and get the last part of the URL
        return url.strip('/').split('/')[-1]
    
    def update_navigation(self):
        """Update navigation buttons and page label"""
        total_pages = max(1, (len(self.filtered_anime) + self.items_per_page - 1) // self.items_per_page)
        
        # Update page label
        self.page_label.configure(text=f"Sayfa {self.current_page}/{total_pages}")
        
        # Enable/disable navigation buttons
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")
    
    def prev_page(self):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.display_current_page()
    
    def next_page(self):
        """Go to next page"""
        total_pages = (len(self.filtered_anime) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_current_page()
    
    def on_search_change(self):
        """Handle search input changes"""
        search_term = self.search_var.get()
        self.filter_anime(search_term)
        self.display_current_page()
    
    def on_anime_select(self, anime_slug):
        """Handle anime selection based on mode"""
        try:
            print(f"Loading anime: {anime_slug}")  # Debug print
            
            # Add more detailed debugging
            if self.mode == "watch":
                print(f"Mode: watch - Attempting to show episode list")
                episodes = self.app.get_episode_list(anime_slug)  # Add this method if it doesn't exist
                print(f"Found {len(episodes) if episodes else 0} episodes")
                self.app.show_episode_list(anime_slug)
            else:
                print(f"Mode: download - Attempting to show download episodes")
                episodes = self.app.get_download_episodes(anime_slug)  # Add this method if it doesn't exist
                print(f"Found {len(episodes) if episodes else 0} episodes")
                self.app.show_download_episodes(anime_slug)
            
        except IndexError as e:
            error_message = (
                f"Bölüm listesi yüklenirken hata oluştu:\n"
                f"Anime için bölüm bulunamadı. ({anime_slug})\n"
                f"Detaylı hata: {str(e)}"
            )
            print(f"Error loading episodes: IndexError - {str(e)}")
            print(f"Error location: {e.__traceback__.tb_frame.f_code.co_filename}:{e.__traceback__.tb_lineno}")
            self.show_error(error_message)
        except Exception as e:
            error_message = (
                f"Bölüm listesi yüklenirken hata oluştu:\n"
                f"Hata türü: {type(e).__name__}\n"
                f"Hata mesajı: {str(e)}"
            )
            print(f"Error loading episodes: {type(e).__name__} - {str(e)}")
            print(f"Error location: {e.__traceback__.tb_frame.f_code.co_filename}:{e.__traceback__.tb_lineno}")
            self.show_error(error_message)
    
    def show_error(self, message):
        """Show error dialog"""
        error_window = ctk.CTkToplevel(self)
        error_window.title("Hata")
        error_window.geometry("400x150")
        
        # Make the window modal
        error_window.transient(self)
        error_window.grab_set()
        
        # Center the window
        error_window.update_idletasks()
        width = error_window.winfo_width()
        height = error_window.winfo_height()
        x = (error_window.winfo_screenwidth() // 2) - (width // 2)
        y = (error_window.winfo_screenheight() // 2) - (height // 2)
        error_window.geometry(f'{width}x{height}+{x}+{y}')
        
        error_label = ctk.CTkLabel(
            error_window,
            text=message,
            text_color="red",
            wraplength=350  # Allow text to wrap
        )
        error_label.pack(pady=20)
        
        ok_button = ctk.CTkButton(
            error_window,
            text="Tamam",
            command=error_window.destroy
        )
        ok_button.pack(pady=10)
    
    def load_anime(self, anime_slug):
        """Load anime episodes"""
        try:
            print(f"Loading anime: {anime_slug}")
            print(f"Mode: {self.mode} - Attempting to show episode list")
            
            # Get episodes
            episodes = self.app.get_episode_list(anime_slug)
            
            # Show episodes in UI
            if episodes:
                self.episode_list.show_episodes(episodes)
            
        except Exception as error:
            print(f"Error loading episodes: {type(error).__name__} - {str(error)}")
            print(f"Error location: {__file__}:{sys.exc_info()[2].tb_lineno}")
            self.episode_list.show_error(f"Bölümler yüklenemedi:\n{str(error)}")