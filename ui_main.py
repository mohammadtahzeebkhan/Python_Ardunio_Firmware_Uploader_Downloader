import os
import threading
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.tooltip import ToolTip   # ✅ for tooltip
from flash_utils import (
    get_ports, flash_firmware, flash_avr, read_firmware_esp, read_firmware_avr,
    get_chip_id, get_board_info_esp, get_board_info_avr, OTA_FIRMWARE, BLINK_FIRMWARE, BOARD_CONFIGS,
)
from widgets import log_message
from app_settings import load_settings, save_settings
from serial_monitor import open_serial_monitor
import tkinter as tk   # for log_box.insert(tk.END,...)

# globals for tracking
current_ports = []
is_flashing = False

BAUD_RATES = ["9600", "57600", "115200", "230400", "460800", "921600"]
BOARD_NAMES = ["ESP8266"] + list(BOARD_CONFIGS.keys())
FLASH_SIZES = {
    "512KB": 0x80000,
    "1MB": 0x100000,
    "2MB": 0x200000,
    "4MB": 0x400000,
    "8MB": 0x800000,
    "16MB": 0x1000000,
}


def create_main_page(container, switch_page, about_frame=None):
    settings = load_settings()

    main_frame = ttk.Frame(container)

    # ===== Board Selection =====
    board_frame = ttk.LabelFrame(main_frame, text="Board")
    board_frame.pack(fill="x", padx=20, pady=(15, 8))

    ttk.Label(board_frame, text="Target:").pack(side="left", padx=(8, 5), pady=8)
    board_combo = ttk.Combobox(board_frame, values=BOARD_NAMES, width=20, state="readonly")
    board_combo.set(settings.get("board", "ESP8266") if settings.get("board", "ESP8266") in BOARD_NAMES else "ESP8266")
    board_combo.pack(side="left", padx=5, pady=8)

    # shown only for ESP8266 -- avrdude reads AVR flash size from the chip signature
    flash_size_frame = ttk.Frame(board_frame)
    ttk.Label(flash_size_frame, text="Flash Size:").pack(side="left", padx=(0, 5))
    flash_size_combo = ttk.Combobox(flash_size_frame, values=list(FLASH_SIZES.keys()), width=8, state="readonly")
    flash_size_combo.set(settings.get("flash_size", "4MB") if settings.get("flash_size", "4MB") in FLASH_SIZES else "4MB")
    flash_size_combo.pack(side="left")
    ToolTip(flash_size_frame, text="Used when backing up (reading) firmware from an ESP8266")

    # ===== File Selection =====
    file_frame = ttk.LabelFrame(main_frame, text="Firmware File")
    file_frame.pack(fill="x", padx=20, pady=8)

    file_entry = ttk.Entry(file_frame, width=55)
    file_entry.pack(side="left", padx=8, pady=8, fill="x", expand=True)
    if settings.get("firmware") and os.path.isfile(settings["firmware"]):
        file_entry.insert(0, settings["firmware"])

    def browse_file():
        if board_combo.get() == "ESP8266":
            filetypes = [("BIN files", "*.bin"), ("All files", "*.*")]
        else:
            filetypes = [("HEX files", "*.hex"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            file_entry.delete(0, "end")
            file_entry.insert(0, filename)

    ttk.Button(file_frame, text="Browse", bootstyle="secondary", command=browse_file).pack(side="left", padx=8, pady=8)

    # ===== Port / Baud Selection =====
    port_frame = ttk.LabelFrame(main_frame, text="Connection")
    port_frame.pack(fill="x", padx=20, pady=8)

    ttk.Label(port_frame, text="Port:").pack(side="left", padx=(8, 5), pady=8)
    port_combo = ttk.Combobox(port_frame, values=get_ports(), width=16, state="readonly")
    port_combo.pack(side="left", padx=5, pady=8)

    def refresh_ports():
        ports = get_ports()
        port_combo["values"] = ports
        log_message(log_box, "Ports refreshed: " + (", ".join(ports) if ports else "None"), "info")
        if settings.get("port") in ports:
            port_combo.set(settings["port"])

    ttk.Button(port_frame, text="🔄 Refresh", bootstyle="secondary", command=refresh_ports).pack(side="left", padx=5, pady=8)

    ttk.Label(port_frame, text="Baud:").pack(side="left", padx=(20, 5), pady=8)
    baud_combo = ttk.Combobox(port_frame, values=BAUD_RATES, width=10, state="readonly")
    baud_combo.set(settings.get("baud", "115200"))
    baud_combo.pack(side="left", padx=5, pady=8)

    # preselect last-used port if it's currently available
    if settings.get("port") in port_combo["values"]:
        port_combo.set(settings["port"])

    # ===== Chip ID Display =====
    chipid_label = ttk.Label(main_frame, text="🔎 Chip ID: Not Detected", font=("Segoe UI", 10, "bold"))
    chipid_label.pack(pady=6)

    # ===== Tools: Board Info / Serial Monitor =====
    tools_frame = ttk.Frame(main_frame)
    tools_frame.pack(pady=(0, 6))

    monitor_state = {"window": None}

    def start_board_info():
        global is_flashing

        if is_flashing:
            messagebox.showinfo("Busy", "Please wait for the current operation to finish first.")
            return

        board = board_combo.get()
        port = port_combo.get()
        baud = baud_combo.get()

        if not port:
            messagebox.showerror("Error", "Please select a COM port first.")
            return

        is_flashing = True
        set_action_buttons_state("disabled")
        status_bar.config(text="🔍 Reading board info...", bootstyle="info")

        def run_info():
            global is_flashing
            if board == "ESP8266":
                ok = get_board_info_esp(port, baud, log_box)
            else:
                ok = get_board_info_avr(port, baud, board, log_box)
            is_flashing = False
            set_action_buttons_state("normal")
            if ok:
                status_bar.config(text="✅ Board info retrieved", bootstyle="success")
            else:
                status_bar.config(text="❌ Could not read board info. Check log.", bootstyle="danger")

        threading.Thread(target=run_info, daemon=True).start()

    def start_monitor():
        global is_flashing

        if is_flashing:
            messagebox.showinfo("Busy", "Please wait for the current operation to finish first.")
            return

        port = port_combo.get()
        baud = baud_combo.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port first.")
            return

        def on_monitor_close():
            global is_flashing
            is_flashing = False
            monitor_state["window"] = None
            set_action_buttons_state("normal")
            status_bar.config(text="⚡ Ready", bootstyle="light")

        is_flashing = True
        set_action_buttons_state("disabled")
        status_bar.config(text=f"🖥 Serial monitor connected to {port}", bootstyle="info")

        win = open_serial_monitor(main_frame, port, baud, on_close=on_monitor_close)
        monitor_state["window"] = win
        if win is None:
            on_monitor_close()

    board_info_btn = ttk.Button(tools_frame, text="🔍 Board Info", bootstyle="secondary", command=start_board_info)
    board_info_btn.grid(row=0, column=0, padx=8)
    ToolTip(board_info_btn, text="Query the connected board's identity without flashing anything")

    monitor_btn = ttk.Button(tools_frame, text="🖥 Serial Monitor", bootstyle="secondary", command=start_monitor)
    monitor_btn.grid(row=0, column=1, padx=8)
    ToolTip(monitor_btn, text="Open a live serial monitor for the selected port/baud")

    # ===== Flash / About / Cancel Buttons =====
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(pady=6)

    progress = ttk.Progressbar(main_frame, mode="determinate", maximum=100)
    progress.pack(fill="x", padx=20, pady=8)

    # ===== Log Section =====
    log_header = ttk.Frame(main_frame)
    log_header.pack(fill="x", padx=20)
    ttk.Label(log_header, text="Log", font=("Segoe UI", 9, "bold")).pack(side="left")

    def clear_log():
        log_box.delete("1.0", tk.END)

    def copy_log():
        main_frame.clipboard_clear()
        main_frame.clipboard_append(log_box.get("1.0", tk.END))

    ttk.Button(log_header, text="Copy", bootstyle="link", command=copy_log).pack(side="right")
    ttk.Button(log_header, text="Clear", bootstyle="link", command=clear_log).pack(side="right")

    log_box = ttk.Text(main_frame, height=12)
    log_box.pack(fill="both", expand=True, padx=20, pady=(4, 10))

    status_bar = ttk.Label(main_frame, text="⚡ Ready", anchor="w", bootstyle="inverse-light")
    status_bar.pack(fill="x", side="bottom")

    # ===== Detect COM port changes =====
    def detect_port_change():
        """Always update port list. Reset chip ID if no device is connected."""
        global current_ports, is_flashing

        ports = get_ports()
        if ports != current_ports:
            current_ports = ports
            port_combo["values"] = ports
            log_message(log_box, "COM ports changed: " + (", ".join(ports) if ports else "None"), "info")

            if not is_flashing and board_combo.get() == "ESP8266":
                if ports:  # at least one port available
                    detected = False
                    baud = baud_combo.get()
                    for port in ports:
                        if get_chip_id(port, baud, log_box, chipid_label):
                            port_combo.set(port)
                            detected = True
                            break
                    if not detected:
                        chipid_label.config(text="🔎 Chip ID: Not Detected")
                else:
                    # 🚨 No ports connected → reset Chip ID
                    chipid_label.config(text="🔎 Chip ID: Not Detected")

        # run again in 2s
        main_frame.after(2000, detect_port_change)

    # start port change watcher
    detect_port_change()

    cancel_event = threading.Event()

    def set_action_buttons_state(state):
        flash_btn.config(state=state)
        ota_btn.config(state=state)
        blink_btn.config(state=state)
        backup_btn.config(state=state)
        board_info_btn.config(state=state)
        monitor_btn.config(state=state)

    # ===== Generic Flash function =====
    def start_flash(firmware_file=None):
        global is_flashing

        fw = firmware_file or file_entry.get()
        port = port_combo.get()
        baud = baud_combo.get()
        board = board_combo.get()

        if not fw:
            messagebox.showerror("Error", "Please select a firmware file first.")
            return
        if not port:
            messagebox.showerror("Error", "Please select a COM port first.")
            return

        confirm_msg = f"Flash {board} firmware to {port} at {baud} baud?\n\n{os.path.basename(fw)}"

        if not messagebox.askyesno("Confirm Flash", confirm_msg):
            return

        cancel_event.clear()
        is_flashing = True
        set_action_buttons_state("disabled")
        cancel_btn.config(state="normal")
        status_bar.config(text="⏳ Uploading firmware...", bootstyle="info")

        def run_flash():
            global is_flashing
            if board == "ESP8266":
                result = flash_firmware(port, baud, fw, progress, log_box, cancel_event)
            else:
                result = flash_avr(port, baud, fw, board, progress, log_box, cancel_event)
            is_flashing = False
            set_action_buttons_state("normal")
            cancel_btn.config(state="disabled")

            if result == "success":
                status_bar.config(text="✅ Flash completed successfully", bootstyle="success")
            elif result == "cancelled":
                status_bar.config(text="⏹ Flash cancelled", bootstyle="warning")
            else:
                status_bar.config(text="❌ Flash failed. Check log.", bootstyle="danger")

        threading.Thread(target=run_flash, daemon=True).start()

    def cancel_flash():
        cancel_event.set()
        status_bar.config(text="⏹ Cancelling...", bootstyle="warning")

    # ===== Backup (read firmware off the board) =====
    def start_backup():
        global is_flashing

        board = board_combo.get()
        port = port_combo.get()
        baud = baud_combo.get()

        if not port:
            messagebox.showerror("Error", "Please select a COM port first.")
            return

        if board == "ESP8266":
            default_ext = ".bin"
            filetypes = [("BIN files", "*.bin")]
        else:
            default_ext = ".hex"
            filetypes = [("HEX files", "*.hex")]

        save_path = filedialog.asksaveasfilename(
            title="Save firmware backup as",
            defaultextension=default_ext,
            filetypes=filetypes,
        )
        if not save_path:
            return

        if not messagebox.askyesno(
            "Confirm Backup",
            f"Read firmware from {port} ({board}) and save to:\n\n{save_path}?"
        ):
            return

        cancel_event.clear()
        is_flashing = True
        set_action_buttons_state("disabled")
        cancel_btn.config(state="normal")
        status_bar.config(text="⏳ Reading firmware from device...", bootstyle="info")

        def run_backup():
            global is_flashing
            if board == "ESP8266":
                size_bytes = FLASH_SIZES.get(flash_size_combo.get(), 0x400000)
                result = read_firmware_esp(port, baud, save_path, size_bytes, progress, log_box, cancel_event)
            else:
                result = read_firmware_avr(port, baud, save_path, board, progress, log_box, cancel_event)
            is_flashing = False
            set_action_buttons_state("normal")
            cancel_btn.config(state="disabled")

            if result == "success":
                status_bar.config(text="✅ Backup completed successfully", bootstyle="success")
                messagebox.showinfo("Backup Complete", f"Firmware saved to:\n{save_path}")
            elif result == "cancelled":
                status_bar.config(text="⏹ Backup cancelled", bootstyle="warning")
            else:
                status_bar.config(text="❌ Backup failed. Check log.", bootstyle="danger")

        threading.Thread(target=run_backup, daemon=True).start()

    # ===== Buttons =====
    flash_btn = ttk.Button(btn_frame, text="⚡ Flash Firmware", bootstyle="success", command=lambda: start_flash())
    flash_btn.grid(row=0, column=0, padx=8)
    ToolTip(flash_btn, text="Flash firmware from the file you selected")

    ota_btn = ttk.Button(btn_frame, text="⚡ Flash OTA", bootstyle="secondary", command=lambda: start_flash(OTA_FIRMWARE))
    ota_btn.grid(row=0, column=1, padx=8)
    ToolTip(ota_btn, text="Flash the built-in OTA firmware")

    blink_btn = ttk.Button(btn_frame, text="⚡ Flash Blink", bootstyle="secondary", command=lambda: start_flash(BLINK_FIRMWARE))
    blink_btn.grid(row=0, column=2, padx=8)
    ToolTip(blink_btn, text="Flash the built-in Blink firmware")

    backup_btn = ttk.Button(btn_frame, text="⬇ Backup Firmware", bootstyle="warning", command=start_backup)
    backup_btn.grid(row=0, column=3, padx=8)
    ToolTip(backup_btn, text="Read the firmware currently on the board and save it to a file you choose")

    cancel_btn = ttk.Button(btn_frame, text="⏹ Cancel", bootstyle="danger", command=cancel_flash, state="disabled")
    cancel_btn.grid(row=0, column=4, padx=8)
    ToolTip(cancel_btn, text="Stop the operation currently in progress")

    about_btn = ttk.Button(btn_frame, text="ℹ️ About", bootstyle="info", command=lambda: switch_page("about"))
    about_btn.grid(row=0, column=5, padx=8)
    ToolTip(about_btn, text="About this tool")

    # ===== Board-specific UI toggling =====
    def on_board_change(event=None):
        board = board_combo.get()
        is_esp = board == "ESP8266"

        if is_esp:
            flash_size_frame.pack(side="left", padx=(20, 5), pady=8)
            ota_btn.grid(row=0, column=1, padx=8)
            blink_btn.grid(row=0, column=2, padx=8)
            chipid_label.config(text="🔎 Chip ID: Not Detected")
        else:
            flash_size_frame.pack_forget()
            ota_btn.grid_remove()
            blink_btn.grid_remove()
            chipid_label.config(text=f"🔧 {board} selected — select port manually")

    board_combo.bind("<<ComboboxSelected>>", on_board_change)
    on_board_change()

    # ===== Persist settings on app close =====
    def persist_settings():
        save_settings({
            "board": board_combo.get(),
            "port": port_combo.get(),
            "baud": baud_combo.get(),
            "flash_size": flash_size_combo.get(),
            "firmware": file_entry.get(),
        })

    main_frame.persist_settings = persist_settings

    return main_frame
