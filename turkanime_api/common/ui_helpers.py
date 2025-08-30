# -*- coding: utf-8 -*-
"""
Ortak UI yardımcı fonksiyonları.
"""
import customtkinter as ctk


def create_progress_section(parent, pad_x=20, pad_y=(0, 20)):
    """Progress bar ve button frame bölümlerini oluşturur ve return eder."""
    progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
    progress_frame.pack(fill="x", padx=pad_x, pady=pad_y)

    progress_label = ctk.CTkLabel(progress_frame, text="")
    progress_label.pack()

    progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
    progress_bar.pack(pady=(10, 0))
    progress_bar.set(0)

    buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
    buttons_frame.pack(fill="x", padx=pad_x, pady=pad_y)

    return progress_label, progress_bar, buttons_frame
