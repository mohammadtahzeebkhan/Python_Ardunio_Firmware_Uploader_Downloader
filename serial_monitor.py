import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
import serial

LINE_ENDINGS = {
    "None": b"",
    "\\n": b"\n",
    "\\r": b"\r",
    "\\r\\n": b"\r\n",
}

BAUD_RATES = ["9600", "57600", "115200", "230400", "460800", "921600"]


def open_serial_monitor(parent, port, baud, on_close=None):
    """Open a serial monitor window for `port`, with a live baud-rate selector and send box.

    Returns the Toplevel on success, or None if the initial connection failed
    (in which case `on_close` is still invoked so callers can reset their state).
    """
    win = ttk.Toplevel(parent)
    win.title(f"Serial Monitor — {port}")
    win.geometry("640x460")

    # ===== Top bar: port label + live baud selector =====
    top = ttk.Frame(win)
    top.pack(fill="x", padx=8, pady=(8, 4))

    ttk.Label(top, text=f"Port: {port}").pack(side="left")
    ttk.Label(top, text="Baud:").pack(side="left", padx=(15, 5))
    baud_var = tk.StringVar(value=str(baud) if str(baud) in BAUD_RATES else BAUD_RATES[2])
    baud_combo = ttk.Combobox(top, textvariable=baud_var, values=BAUD_RATES, width=10, state="readonly")
    baud_combo.pack(side="left")

    status_label = ttk.Label(top, text="", bootstyle="secondary")
    status_label.pack(side="left", padx=15)

    text = ttk.Text(win, height=20)
    text.pack(fill="both", expand=True, padx=8, pady=4)

    bottom = ttk.Frame(win)
    bottom.pack(fill="x", padx=8, pady=(0, 8))

    autoscroll_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(bottom, text="Autoscroll", variable=autoscroll_var, bootstyle="round-toggle").pack(side="left")

    line_ending_var = tk.StringVar(value="\\n")
    ttk.Combobox(
        bottom, textvariable=line_ending_var, values=list(LINE_ENDINGS.keys()), width=6, state="readonly"
    ).pack(side="left", padx=5)

    send_entry = ttk.Entry(bottom)
    send_entry.pack(side="left", fill="x", expand=True, padx=5)

    # ===== Connection state (rebuilt whenever the baud rate changes) =====
    state = {"ser": None, "stop_flag": None}

    def reader_loop(ser, stop_flag):
        while not stop_flag.is_set():
            try:
                data = ser.read(256)
            except Exception:
                break
            if data:
                text.insert("end", data.decode(errors="replace"))
                if autoscroll_var.get():
                    text.see("end")

    def disconnect():
        if state["stop_flag"]:
            state["stop_flag"].set()
        if state["ser"]:
            try:
                state["ser"].close()
            except Exception:
                pass
        state["ser"] = None
        state["stop_flag"] = None

    def connect(baud_value):
        disconnect()
        try:
            ser = serial.Serial(port, int(baud_value), timeout=0.1)
        except Exception as e:
            status_label.config(text=f"⚠ {e}", bootstyle="danger")
            return False

        stop_flag = threading.Event()
        state["ser"] = ser
        state["stop_flag"] = stop_flag
        threading.Thread(target=reader_loop, args=(ser, stop_flag), daemon=True).start()

        status_label.config(text=f"Connected at {baud_value} baud", bootstyle="success")
        text.insert("end", f"\n[connected at {baud_value} baud]\n")
        return True

    def on_baud_change(event=None):
        connect(baud_var.get())

    baud_combo.bind("<<ComboboxSelected>>", on_baud_change)

    def send(event=None):
        data = send_entry.get()
        if not data or not state["ser"]:
            return
        try:
            state["ser"].write(data.encode() + LINE_ENDINGS[line_ending_var.get()])
            send_entry.delete(0, "end")
        except Exception as e:
            text.insert("end", f"\n[send error: {e}]\n")

    send_entry.bind("<Return>", send)
    ttk.Button(bottom, text="Send", bootstyle="success", command=send).pack(side="left", padx=5)
    ttk.Button(bottom, text="Clear", bootstyle="secondary", command=lambda: text.delete("1.0", "end")).pack(
        side="left", padx=5
    )

    if not connect(baud_var.get()):
        messagebox.showerror("Serial Monitor", f"Could not open {port} at {baud_var.get()} baud.")
        win.destroy()
        if on_close:
            on_close()
        return None

    def handle_close():
        disconnect()
        win.destroy()
        if on_close:
            on_close()

    win.protocol("WM_DELETE_WINDOW", handle_close)
    win.close_monitor = handle_close  # lets callers close this programmatically (e.g. a Disconnect button)
    return win
