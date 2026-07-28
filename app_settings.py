import json
import os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".esp8266_uploader_settings.json")

DEFAULTS = {
    "board": "ESP8266",
    "port": "",
    "baud": "115200",
    "flash_size": "4MB",
    "firmware": "",
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            merged = DEFAULTS.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULTS.copy()


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
