import re
import subprocess
import sys
import os
import serial.tools.list_ports
from tkinter import messagebox

from widgets import log_message

PERCENT_RE = re.compile(r"(\d{1,3})\s*%")

# avrdude.exe (and, in dev mode, python.exe) are console-subsystem programs. Even with
# stdout piped, Windows still flashes a console window for them unless this is set.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# ===== AVR board definitions (Arduino boards, flashed via avrdude) =====
# "profiles" are tried in order, each optionally overriding the UI-selected baud:
#  - Mega2560 clones (esp. CH340-based) often ship an optiboot bootloader that speaks
#    "arduino" (stk500v1) instead of the genuine board's "wiring" (stk500v2) bootloader.
#  - Nano clones often have an older bootloader that only syncs at 57600, not 115200.
#  - Leonardo/Micro use the atmega32u4's USB-CDC "Caterina" bootloader (avr109 protocol),
#    which is fixed at 57600 baud regardless of what's selected in the UI.
BOARD_CONFIGS = {
    "Arduino Uno": {
        "mcu": "atmega328p",
        "profiles": [{"programmer": "arduino"}],
    },
    "Arduino Nano": {
        "mcu": "atmega328p",
        "profiles": [{"programmer": "arduino"}, {"programmer": "arduino", "baud": "57600"}],
    },
    "Arduino Mega 2560": {
        "mcu": "atmega2560",
        "profiles": [{"programmer": "wiring"}, {"programmer": "arduino"}],
    },
    "Arduino Leonardo": {
        "mcu": "atmega32u4",
        "profiles": [{"programmer": "avr109", "baud": "57600"}],
    },
    "Arduino Micro": {
        "mcu": "atmega32u4",
        "profiles": [{"programmer": "avr109", "baud": "57600"}],
    },
}

_avrdude_cache = None


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller .exe"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# === Predefined firmware files ===
BASE_DIR = os.path.dirname(__file__)   # finalcode/ ka path
OTA_FIRMWARE = os.path.join(BASE_DIR, "ota.bin")
BLINK_FIRMWARE = os.path.join(BASE_DIR, "blink.bin")


# ===== Get available COM ports =====
def get_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def _esptool_base_cmd():
    """Command prefix to invoke esptool, whether running from source or frozen.

    A frozen main.exe is a onefile bundle -- sys.executable is main.exe itself,
    so "-m esptool" can't work there. The frozen build ships a sibling
    esptool_helper.exe (see main.spec) for that case instead.
    """
    if getattr(sys, "frozen", False):
        return [os.path.join(os.path.dirname(sys.executable), "esptool_helper.exe")]
    return [sys.executable, "-m", "esptool"]


def find_avrdude():
    """Locate avrdude.exe + avrdude.conf bundled with an installed Arduino IDE."""
    global _avrdude_cache
    if _avrdude_cache is not None:
        return _avrdude_cache

    search_roots = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Arduino15", "packages"),
        r"C:\Program Files (x86)\Arduino\hardware\tools\avr",
        r"C:\Program Files\Arduino IDE",
    ]

    exe_path = None
    for root_dir in search_roots:
        if not os.path.isdir(root_dir):
            continue
        for root, _dirs, files in os.walk(root_dir):
            if "avrdude.exe" in files:
                exe_path = os.path.join(root, "avrdude.exe")
                break
        if exe_path:
            break

    conf_path = None
    if exe_path:
        bin_dir = os.path.dirname(exe_path)
        sibling_conf = os.path.join(os.path.dirname(bin_dir), "etc", "avrdude.conf")
        if os.path.isfile(sibling_conf):
            conf_path = sibling_conf
        else:
            for root, _dirs, files in os.walk(os.path.dirname(bin_dir)):
                if "avrdude.conf" in files:
                    conf_path = os.path.join(root, "avrdude.conf")
                    break

    _avrdude_cache = (exe_path, conf_path)
    return _avrdude_cache


def _run_device_process(cmd, progress, log_box, cancel_event, verb="Flash"):
    """Run a flash/read subprocess, streaming output to the log and progress bar."""
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=_NO_WINDOW,
    )

    for line in process.stdout:
        if cancel_event.is_set():
            process.terminate()
            process.wait()
            log_message(log_box, f"{verb} cancelled by user", "warning")
            return "cancelled"

        log_box.insert("end", line)
        log_box.see("end")

        match = PERCENT_RE.search(line)
        if match:
            progress["value"] = int(match.group(1))

    process.wait()

    if process.returncode == 0:
        progress["value"] = 100
        log_message(log_box, f"{verb} completed successfully!", "success")
        return "success"
    else:
        log_message(log_box, f"{verb} failed!", "error")
        return "failed"


def _build_avrdude_cmd(avrdude_exe, avrdude_conf, mcu, programmer, port, baud, action, extra_flags=None):
    cmd = [avrdude_exe]
    if avrdude_conf:
        cmd += ["-C", avrdude_conf]
    cmd += ["-p", mcu, "-c", programmer, "-P", port, "-b", str(baud)]
    cmd += extra_flags or []
    cmd += ["-U", action]
    return cmd


def _run_avr_process_with_fallback(config, avrdude_exe, avrdude_conf, port, baud, action,
                                    progress, log_box, cancel_event, verb, extra_flags=None):
    """Try each connection profile for this board in order, falling back on sync failure
    (common on clone boards running a different bootloader than the genuine board, or
    an older bootloader that only syncs at a lower baud rate)."""
    profiles = config["profiles"]
    result = "failed"

    for i, profile in enumerate(profiles):
        if cancel_event.is_set():
            log_message(log_box, f"{verb} cancelled by user", "warning")
            return "cancelled"

        programmer = profile["programmer"]
        effective_baud = profile.get("baud", baud)

        log_message(log_box, f"Using programmer '{programmer}' at {effective_baud} baud...", "info")
        cmd = _build_avrdude_cmd(avrdude_exe, avrdude_conf, config["mcu"], programmer, port, effective_baud, action, extra_flags)
        result = _run_device_process(cmd, progress, log_box, cancel_event, verb=verb)

        if result != "failed":
            return result

        if i + 1 < len(profiles):
            nxt = profiles[i + 1]
            log_message(
                log_box,
                f"'{programmer}' @ {effective_baud} failed to sync — retrying with "
                f"'{nxt['programmer']}' @ {nxt.get('baud', baud)} "
                "(common on clone boards with a different bootloader)...",
                "warning"
            )

    return result


def _validate_flash_inputs(firmware, port, log_box):
    """Shared pre-flight checks. Returns absolute firmware path, or None if invalid."""
    if not firmware:
        log_message(log_box, "No firmware file selected", "error")
        messagebox.showerror("Error", "No firmware file selected")
        return None

    firmware = os.path.abspath(firmware)

    if not os.path.isfile(firmware):
        log_message(log_box, f"Firmware file not found: {firmware}", "error")
        messagebox.showerror("Error", f"Firmware not found:\n{firmware}")
        return None

    if not port:
        log_message(log_box, "No COM port selected", "error")
        messagebox.showerror("Error", "No COM port selected")
        return None

    return firmware


# ===== Flash ESP8266 firmware (via esptool) =====
def flash_firmware(port, baud, firmware, progress, log_box, cancel_event):
    """Flash `firmware` to `port` on an ESP8266. Returns "success", "failed", or "cancelled"."""
    try:
        firmware = _validate_flash_inputs(firmware, port, log_box)
        if firmware is None:
            return "failed"

        progress["value"] = 0
        log_message(log_box, f"Starting flash on {port} at {baud} baud (ESP8266)...", "info")
        log_message(log_box, f"Using firmware: {firmware}", "info")

        cmd = _esptool_base_cmd() + [
            "--chip", "esp8266", "--port", port, "--baud", str(baud),
            "write_flash", "-z", "0x00000", firmware
        ]

        return _run_device_process(cmd, progress, log_box, cancel_event, verb="Flash")

    except Exception as e:
        log_message(log_box, f"Error: {e}", "error")
        return "failed"


# ===== Flash Arduino Uno / Mega firmware (via avrdude) =====
def flash_avr(port, baud, firmware, board, progress, log_box, cancel_event):
    """Flash `firmware` (.hex) to `port` on an AVR board. Returns "success", "failed", or "cancelled"."""
    try:
        firmware = _validate_flash_inputs(firmware, port, log_box)
        if firmware is None:
            return "failed"

        config = BOARD_CONFIGS.get(board)
        if not config:
            log_message(log_box, f"Unknown board: {board}", "error")
            return "failed"

        avrdude_exe, avrdude_conf = find_avrdude()
        if not avrdude_exe:
            log_message(log_box, "avrdude not found. Install the Arduino IDE and try again.", "error")
            messagebox.showerror(
                "avrdude not found",
                "Could not locate avrdude.exe.\nInstall the Arduino IDE (which bundles avrdude) and try again."
            )
            return "failed"

        progress["value"] = 0
        log_message(log_box, f"Starting flash on {port} at {baud} baud ({board})...", "info")
        log_message(log_box, f"Using firmware: {firmware}", "info")

        return _run_avr_process_with_fallback(
            config, avrdude_exe, avrdude_conf, port, baud, f"flash:w:{firmware}:i",
            progress, log_box, cancel_event, verb="Flash", extra_flags=["-v", "-D"]
        )

    except Exception as e:
        log_message(log_box, f"Error: {e}", "error")
        return "failed"


# ===== Read/backup firmware from ESP8266 (via esptool) =====
def read_firmware_esp(port, baud, output_path, size_bytes, progress, log_box, cancel_event):
    """Read the flash contents of an ESP8266 into `output_path`. Returns "success", "failed", or "cancelled"."""
    try:
        if not port:
            log_message(log_box, "No COM port selected", "error")
            messagebox.showerror("Error", "No COM port selected")
            return "failed"

        progress["value"] = 0
        log_message(log_box, f"Reading {size_bytes} bytes from {port} at {baud} baud (ESP8266)...", "info")
        log_message(log_box, f"Saving to: {output_path}", "info")

        cmd = _esptool_base_cmd() + [
            "--chip", "esp8266", "--port", port, "--baud", str(baud),
            "read_flash", "0x0", hex(size_bytes), output_path
        ]

        return _run_device_process(cmd, progress, log_box, cancel_event, verb="Backup")

    except Exception as e:
        log_message(log_box, f"Error: {e}", "error")
        return "failed"


# ===== Read/backup firmware from Arduino Uno / Mega (via avrdude) =====
def read_firmware_avr(port, baud, output_path, board, progress, log_box, cancel_event):
    """Read the flash contents of an AVR board into `output_path` (.hex). Returns "success", "failed", or "cancelled"."""
    try:
        if not port:
            log_message(log_box, "No COM port selected", "error")
            messagebox.showerror("Error", "No COM port selected")
            return "failed"

        config = BOARD_CONFIGS.get(board)
        if not config:
            log_message(log_box, f"Unknown board: {board}", "error")
            return "failed"

        avrdude_exe, avrdude_conf = find_avrdude()
        if not avrdude_exe:
            log_message(log_box, "avrdude not found. Install the Arduino IDE and try again.", "error")
            messagebox.showerror(
                "avrdude not found",
                "Could not locate avrdude.exe.\nInstall the Arduino IDE (which bundles avrdude) and try again."
            )
            return "failed"

        progress["value"] = 0
        log_message(log_box, f"Reading firmware from {port} at {baud} baud ({board})...", "info")
        log_message(log_box, f"Saving to: {output_path}", "info")

        return _run_avr_process_with_fallback(
            config, avrdude_exe, avrdude_conf, port, baud, f"flash:r:{output_path}:i",
            progress, log_box, cancel_event, verb="Backup", extra_flags=["-v", "-D"]
        )

    except Exception as e:
        log_message(log_box, f"Error: {e}", "error")
        return "failed"


# ===== Get Chip ID (ESP8266 only) =====
def get_chip_id(port, baud, log_box, chipid_label):
    try:
        cmd = _esptool_base_cmd() + [
            "--chip", "esp8266", "--port", port, "--baud", str(baud),
            "chip_id"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW)
        output = result.stdout.strip()

        for line in output.splitlines():
            if "Chip ID" in line:
                log_message(log_box, f"{port}: {line}", "success")
                chipid_label.config(text=f"🔎 {line}")
                return True
        return False
    except Exception as e:
        log_message(log_box, f"Error reading chip id on {port}: {e}", "error")
        return False


# ===== Board Info: read chip identity without flashing anything =====
def get_board_info_esp(port, baud, log_box):
    """Report full ESP8266 board info (chip, flash id/size, MAC, etc). Returns True/False."""
    try:
        log_message(log_box, f"Reading board info from {port}...", "info")

        info_cmd = _esptool_base_cmd() + ["--chip", "esp8266", "--port", port, "--baud", str(baud), "chip_id"]
        flash_cmd = _esptool_base_cmd() + ["--chip", "esp8266", "--port", port, "--baud", str(baud), "flash_id"]

        found = False
        for cmd in (info_cmd, flash_cmd):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
            output = result.stdout.strip()
            if output:
                for line in output.splitlines():
                    log_box.insert("end", line + "\n")
                    found = True
                log_box.see("end")

        if not found:
            log_message(log_box, f"Could not read board info from {port}", "error")
        return found

    except Exception as e:
        log_message(log_box, f"Error reading board info: {e}", "error")
        return False


def get_board_info_avr(port, baud, board, log_box):
    """Report the AVR device signature avrdude sees on connect. Returns True/False.

    Tries each candidate programmer for this board (see BOARD_CONFIGS) -- whichever one
    gets a signature back also tells you which bootloader protocol the board actually uses,
    which is the same mismatch that causes stk500_getsync failures during flash/backup.
    """
    try:
        config = BOARD_CONFIGS.get(board)
        if not config:
            log_message(log_box, f"Unknown board: {board}", "error")
            return False

        avrdude_exe, avrdude_conf = find_avrdude()
        if not avrdude_exe:
            log_message(log_box, "avrdude not found. Install the Arduino IDE and try again.", "error")
            return False

        log_message(log_box, f"Reading board info from {port}...", "info")

        tried = []
        for profile in config["profiles"]:
            programmer = profile["programmer"]
            effective_baud = profile.get("baud", baud)
            tried.append(f"{programmer}@{effective_baud}")

            cmd = [avrdude_exe]
            if avrdude_conf:
                cmd += ["-C", avrdude_conf]
            # -v -v for verbose part descriptions too (fuses, memory sizes, etc), not just the signature line
            cmd += ["-v", "-v", "-p", config["mcu"], "-c", programmer, "-P", port, "-b", str(effective_baud)]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
                combined = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                log_message(log_box, f"'{programmer}' @ {effective_baud} timed out, trying next...", "warning")
                continue

            if "Device signature" in combined:
                log_message(log_box, f"--- programmer: {programmer} @ {effective_baud} baud ---", "info")
                for line in combined.splitlines():
                    log_box.insert("end", line + "\n")
                log_box.see("end")
                return True

        log_message(
            log_box,
            f"Could not read a device signature from {port} (tried: {', '.join(tried)})",
            "error"
        )
        return False

    except Exception as e:
        log_message(log_box, f"Error reading board info: {e}", "error")
        return False
