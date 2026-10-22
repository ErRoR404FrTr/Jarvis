""" This is the Python file containing the functions that main will use, based on the actions. """
""" More functions are coming... """

# Libraries for using the AI
import json
import subprocess
import time
import sys
import ollama

# Local libraries written by the author
import action as ac
import voice_piper as vx
from app_paths import applications      # List of all applications added by the user (NEED TO CREATE AN "app_paths.py" AND FOLLOW INSTRUCTION IN THE GITHUB)

ollama_process = None

def check_and_start_ollama():
    """Checks whether Ollama is running, otherwise starts it in the background."""
    global ollama_process
    try:
        ollama.list()
        print("[System] Ollama is already running.")
    except Exception:
        print("[System] Starting Ollama automatically...")
        ollama_process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        time.sleep(3)

def close_cleanly():
    """Closes the Ollama process if it was started by this script."""
    global ollama_process
    if ollama_process:
        print("\n[System] Closing Ollama...")
        ollama_process.terminate()
    print("[System] Jarvis offline.")

# Builds the list of applications for the prompt, from the dictionary
def build_apps_text():
    items = []
    for name, (path, process_name, aliases) in applications.items():
        item = name
        if aliases:
            item += " (also called: " + ", ".join(aliases) + ")"
        items.append(item)
    return "; ".join(items)

# You can change the prompt but keep the part after the GOLDEN RULE include
SYSTEM_PROMPT = """
You are Jarvis, Iron Man's AI assistant.
Your style is a mix of subtle humor and light sarcasm, but you are always extremely polite and helpful towards your creator (address him as "sir" in English, "Monsieur" in French and "efendim" in Turkish).

GOLDEN RULE: reply EXCLUSIVELY with a valid JSON object. No text before or after it.

Required format:
{
  "actions": [
    {"type": "brightness", "value": 50},
    {"type": "volume", "value": 30},
    {"type": "execute", "app": "steam"},
    {"type": "kill", "app": "opera"},
    {"type": "reboot"},
    {"type": "shutdown"}
  ],
  "reply": "<your text reply>",
  "lang": "<fr, en or tr>"
}

Rules:
- "actions" is a list, empty [] if there is nothing to do.
- Only use these types: brightness, volume, execute, kill, reboot, shutdown.
- "value" is a number between 0 and 100 (only for brightness and volume).
- "app" must be one of the main names in this list, never invent a name: {APPS}
- If the user asks for an application that is not in the list, say that you cannot open it and leave "actions" empty.
- ALWAYS write "reply" in the language of the user's LAST message (French, English or Turkish), even though these instructions are in English.
- "lang" is the language of "reply": "fr", "en" or "tr".
- Write numbers in words, and use no emojis, no lists and no markdown.
"""

# The {APPS} placeholder is replaced by the real list taken from app_paths.py
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{APPS}", build_apps_text())

# Messages spoken when an action fails ({app} is replaced by the application name)
# Languages can be changed
FAILURE_MESSAGES = {
    "unknown": {
        "fr": "Je ne trouve pas {app} dans ma liste, Monsieur.",
        "en": "I can't find {app} in my list, sir.",
        "tr": "Listemde {app} bulamıyorum efendim.",
    },
    "not_allowed": {
        "fr": "Je n'ai pas l'autorisation de fermer {app}, Monsieur.",
        "en": "I am not allowed to close {app}, sir.",
        "tr": "{app} uygulamasını kapatma iznim yok efendim.",
    },
    "not_running": {
        "fr": "{app} ne semble pas être en cours d'exécution, Monsieur.",
        "en": "{app} does not seem to be running, sir.",
        "tr": "{app} çalışıyor gibi görünmüyor efendim.",
    },
    "error": {
        "fr": "Je n'ai pas réussi à le faire avec {app}, Monsieur.",
        "en": "I could not do that with {app}, sir.",
        "tr": "{app} ile bunu yapamadım efendim.",
    },
}

def failure_text(status, app, language):
    """Builds the spoken message for a failed action, in the right language."""
    messages = FAILURE_MESSAGES.get(status, FAILURE_MESSAGES["error"])
    return messages.get(language, messages["en"]).format(app=app)

# History of conversation (Beta) 
history = []  # memory of the conversation / history
def process_command(user_message):
    try:
        history.append({'role': 'user', 'content': user_message})

        response = ollama.chat(
            model='qwen2.5:7b',
            messages=[{'role': 'system', 'content': SYSTEM_PROMPT}] + history[-10:],
            format='json'
        )

        content = response['message']['content'].strip()
        history.append({'role': 'assistant', 'content': content})
        data = json.loads(content)

        actions = data.get("actions", [])
        failures = []                           # List of (status, app) for the actions that failed

        for action in actions:
            action_type = action.get("type")
            value = action.get("value")
            app = action.get("app")

            if action_type == "brightness" and value is not None:
                ac.change_brightness(value)
            elif action_type == "volume" and value is not None:
                ac.change_volume(value)
            elif action_type == "execute" and app is not None:
                status = ac.launch_app(app)
                if status != "ok":
                    failures.append((status, app))
            elif action_type == "kill" and app is not None:
                status = ac.kill_process(app)
                if status != "ok":
                    failures.append((status, app))
            elif action_type == "reboot":
                ac.reboot()
            elif action_type == "shutdown":
                ac.shutdown_pc()

        reply = data.get("reply")
        language = data.get("lang", vx.DEFAULT_LANGUAGE)

        # If an action failed, the AI's reply ("Opening Chrome, sir...") would be false: we replace it
        if failures:
            language = vx.detect_language(reply or "", language)
            reply = " ".join(failure_text(status, app, language) for status, app in failures)

        print(f"\nJarvis: {reply}\n")
        vx.speak_in_background(reply, language)

    except Exception as e:
        print(f"\n[Error] : {e}")
