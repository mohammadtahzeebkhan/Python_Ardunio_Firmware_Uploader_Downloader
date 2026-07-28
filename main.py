import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH
from PIL import Image, ImageTk
import sys, os

from ui_main import create_main_page
from ui_about import create_about_page


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller exe"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def show_splash(app, callback):
    """Display splash screen and then call callback() to load main UI"""
    app.withdraw()  # Hide main window during splash

    splash = ttk.Toplevel()
    splash.overrideredirect(True)

    # Center splash window
    w, h = 500, 500
    ws, hs = splash.winfo_screenwidth(), splash.winfo_screenheight()
    x, y = (ws // 2 - w // 2), (hs // 2 - h // 2)
    splash.geometry(f"{w}x{h}+{x}+{y}")

    frame = ttk.Frame(splash)
    frame.pack(fill=BOTH, expand=True, padx=20, pady=20)

    # Try loading logo
    try:
        img = Image.open(resource_path("tahzeeb.png"))
        img = img.resize((250, 250))
        splash.img = ImageTk.PhotoImage(img)
        ttk.Label(frame, image=splash.img).pack(pady=10)
    except Exception:
        ttk.Label(frame, text="⚡ Firmware Uploader & Downloader", font=("Segoe UI", 16, "bold")).pack(pady=40)

    ttk.Label(frame, text="🔌 Arduino & ESP8266 Firmware Uploader & Downloader", font=("Segoe UI", 14, "bold")).pack(pady=10)
    ttk.Label(frame, text="Loading, please wait...").pack(pady=5)

    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x", padx=20, pady=15)
    progress.start(10)

    ttk.Label(frame, text="Made by Mohammad Tahzeeb Khan", font=("Segoe UI", 9, "italic")).pack(side="bottom", pady=5)

    # Smooth fade-in
    def fade_in(alpha=0):
        if alpha < 1.0:
            splash.attributes("-alpha", alpha)
            splash.after(30, lambda: fade_in(alpha + 0.05))
    splash.attributes("-alpha", 0)
    fade_in()

    def close_splash():
        splash.destroy()
        app.deiconify()
        callback()

    app.after(2500, close_splash)


def main():
    app = ttk.Window(themename="cyborg")
    app.title("⚡ Arduino & ESP8266 Firmware Uploader & Downloader")
    app.geometry("900x650")
    app.minsize(760, 560)

    try:
        icon_img = ImageTk.PhotoImage(Image.open(resource_path("tahzeeb.png")))
        app.iconphoto(True, icon_img)
        app._icon_img = icon_img  # keep a reference alive
    except Exception:
        pass

    container = ttk.Frame(app)
    container.pack(fill=BOTH, expand=True)

    frames = {}

    def switch_page(page_name):
        if isinstance(page_name, str):
            target = frames[page_name]
        else:
            target = page_name

        for f in frames.values():
            f.pack_forget()
        target.pack(fill=BOTH, expand=True)

    def load_ui():
        main_frame = create_main_page(container, switch_page)
        about_frame = create_about_page(container, switch_page, main_frame)
        frames["main"] = main_frame
        frames["about"] = about_frame
        switch_page("main")

        def on_close():
            try:
                main_frame.persist_settings()
            except Exception:
                pass
            app.destroy()

        app.protocol("WM_DELETE_WINDOW", on_close)

    show_splash(app, load_ui)
    app.mainloop()


if __name__ == "__main__":
    main()
