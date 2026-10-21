""" This Python file contains the actions that the AI can execute. """
""" More functions are coming... """

# Basic libraries for controlling the system
import os
import subprocess

# Libraries for controlling the PC
import screen_brightness_control as sbc     # Brightness
from pycaw.pycaw import AudioUtilities      # Volume
from rapidfuzz import process, fuzz         # Approximate matching of names
import re                                   # Regex

# Python file containing the path and the process name of each application
from app_paths import applications

# Remove everything that is not a letter or a digit: "Opera GX" -> "operagx"
def _normalize(text):
    return re.sub(r"\W+", "", text.lower())

# Lookup table: every name and alias (normalized) -> the main name of the application
_LOOKUP = {}
for _key, (_path, _process, _aliases) in applications.items():
    _LOOKUP[_normalize(_key)] = _key
    for _alias in _aliases:
        _LOOKUP[_normalize(_alias)] = _key

# Find the application matching a name given by the AI
def find_app(app_name, threshold=80):
    """Returns the main name of the matching application, or None.
    Exact match first, then approximate match (threshold from 0 to 100, higher = stricter)."""
    wanted = _normalize(app_name)
    if not wanted:
        return None
    if wanted in _LOOKUP:
        return _LOOKUP[wanted]
    match = process.extractOne(wanted, list(_LOOKUP), scorer=fuzz.ratio, score_cutoff=threshold)
    return _LOOKUP[match[0]] if match else None

# Change the brightness
def change_brightness(value):
    """Changes the screen brightness (0 to 100)"""
    try:
        value = max(0, min(100, int(value)))
        sbc.set_brightness(value)
        print(f"[PC] Brightness set to {value}%")
    except Exception as e:
        print(f"[Brightness Error] : {e}")

# Change the volume
def change_volume(value):
    """Changes the main Windows volume (0 to 100)"""
    try:
        value = max(0, min(100, int(value)))
        # New pycaw syntax
        device = AudioUtilities.GetSpeakers()
        interface = device.EndpointVolume
        interface.SetMasterVolumeLevelScalar(value / 100.0, None)
        print(f"[PC] Volume set to {value}%")
    except Exception as e:
        print(f"[Volume Error] : {e}")

# Launch applications
def launch_app(app_name):
    """Launches applications defined in a dictionary with their absolute path"""
    key = find_app(app_name)
    if key is None:
        print(f"[Launch] Unknown application : {app_name}")
        return "unknown"
    try:
        os.startfile(applications[key][0])
        print(f"[Launch] {key}")
        return "ok"
    except Exception as e:
        print(f"[Launch Error] : {e}")
        return "error"

# Close a process (tricky)
def kill_process(app_name):
    """Closes a running application using its process name, with the Windows taskkill command"""
    key = find_app(app_name, threshold=90)      # Stricter than launching: we do not want to close the wrong app
    if key is None:
        print(f"[Kill] Unknown application : {app_name}")
        return "unknown"
    if applications[key][1] is None:
        print(f"[Kill] Refused : {key} is not allowed")
        return "not_allowed"
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", applications[key][1]],
            stdout = subprocess.DEVNULL,
            stderr = subprocess.DEVNULL,
        )
        if result.returncode != 0:              # taskkill fails when the process is not found
            print(f"[Kill] {key} is not running")
            return "not_running"
        print(f"[Kill] {key}")
        return "ok"
    except Exception as e:
        print(f"[Kill Process Error] : {e}")
        return "error"

# Confirmation
def confirm(question):
    return input(f"{question} (yes/no) : ").strip().lower() in ("yes", "y", "oui", "o", "evet")

# Restart the PC
def reboot():
    """Restarts the PC"""
    if confirm("Restart the PC?"):
        subprocess.run(["shutdown", "/r", "/t", "0"])

# Shut down the PC
def shutdown_pc():
    """Shuts down the PC"""
    if confirm("Shut down the PC?"):
        subprocess.run(["shutdown", "/s", "/t", "0"])
