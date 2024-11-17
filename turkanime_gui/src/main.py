import customtkinter as ctk
from app import App

def main():
    # Set theme and color
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create app instance
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main() 