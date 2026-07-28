import sys
import os
import webbrowser
import ttkbootstrap as ttk
from ttkbootstrap.tooltip import ToolTip
from tkinter.constants import BOTH, LEFT
from PIL import Image, ImageDraw, ImageTk

APP_VERSION = "1.0.0"

DEV_NAME = "Mohammad Tahzeeb Khan"
DEV_ROLE = "Software Developer"
DEV_EMAIL = "mohammadtahzeebkhan@gmail.com"
DEV_PHONE = "+91 7486882890"
YOUTUBE_URL = "https://www.youtube.com/@paradise_hope"


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller exe."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def _circular_avatar(path, size=140):
    """Load an image and mask it into a smooth circle, supersampled for anti-aliasing."""
    scale = 4
    img = Image.open(path).convert("RGBA").resize((size * scale, size * scale))

    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, img.size[0], img.size[1]), fill=255)
    img.putalpha(mask)

    return img.resize((size, size), Image.LANCZOS)


def create_about_page(container, switch_page, main_frame=None):
    about_frame = ttk.Frame(container)
    about_frame.main_frame = main_frame   # store reference to main page

    # ===== Top bar: Back button =====
    top_bar = ttk.Frame(about_frame)
    top_bar.pack(fill="x", padx=20, pady=(15, 0))
    ttk.Button(
        top_bar, text="⬅ Back", bootstyle="link",
        command=lambda: switch_page("main")
    ).pack(side="left")

    # ===== Centered card =====
    card_wrap = ttk.Frame(about_frame)
    card_wrap.pack(fill=BOTH, expand=True)

    card = ttk.Frame(card_wrap, padding=30)
    card.place(relx=0.5, rely=0.5, anchor="center")

    # Avatar
    try:
        avatar_img = ImageTk.PhotoImage(_circular_avatar(resource_path("tahzeeb.png")))
        avatar_label = ttk.Label(card, image=avatar_img)
        avatar_label.image = avatar_img  # keep a reference alive
        avatar_label.pack(pady=(0, 12))
    except Exception:
        ttk.Label(card, text="👤", font=("Segoe UI", 48)).pack(pady=(0, 12))

    ttk.Label(card, text=DEV_NAME, font=("Segoe UI", 18, "bold")).pack()
    ttk.Label(card, text=DEV_ROLE, font=("Segoe UI", 11), bootstyle="secondary").pack(pady=(2, 16))

    ttk.Separator(card).pack(fill="x", pady=(0, 16))

    # Contact rows
    contact_frame = ttk.Frame(card)
    contact_frame.pack(fill="x", pady=(0, 16))

    def contact_row(icon, text, tooltip, on_click=None):
        row = ttk.Frame(contact_frame)
        row.pack(fill="x", pady=3)
        label = ttk.Label(row, text=f"{icon}  {text}", font=("Segoe UI", 10), cursor="hand2" if on_click else "")
        label.pack(anchor="w")
        if on_click:
            label.bind("<Button-1>", lambda e: on_click())
        ToolTip(label, text=tooltip)

    contact_row("📧", DEV_EMAIL, "Click to send an email", lambda: webbrowser.open(f"mailto:{DEV_EMAIL}"))
    contact_row("📱", DEV_PHONE, "Phone number")

    ttk.Button(
        card, text="▶ Visit YouTube Channel", bootstyle="danger",
        command=lambda: webbrowser.open(YOUTUBE_URL)
    ).pack(fill="x", pady=(4, 0))

    ttk.Separator(card).pack(fill="x", pady=16)

    ttk.Label(
        card, text="⚡ Arduino & ESP8266 Firmware Uploader & Downloader",
        font=("Segoe UI", 9, "bold"), bootstyle="secondary", justify=LEFT
    ).pack()
    ttk.Label(card, text=f"Version {APP_VERSION}", font=("Segoe UI", 8), bootstyle="secondary").pack(pady=(2, 0))

    return about_frame
