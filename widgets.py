import tkinter as tk
from datetime import datetime

# ===== Logger to redirect stdout/stderr to Text widget =====
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, string):
        self.widget.insert(tk.END, string, "log")
        self.widget.see(tk.END)
        self.widget.update_idletasks()

    def flush(self):
        pass


TAG_COLORS = {
    "success": "#2ecc71",
    "error": "#e74c3c",
    "warning": "#f1c40f",
    "info": "#5dade2",
}


def log_message(log_box, message, tag=None):
    """Insert a timestamped, optionally color-tagged line into a log Text widget."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"

    if tag and tag not in log_box.tag_names():
        log_box.tag_config(tag, foreground=TAG_COLORS.get(tag, "white"))

    log_box.insert(tk.END, line, tag or "")
    log_box.see(tk.END)
