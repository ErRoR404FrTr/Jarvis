""" This is the Python file that handles Jarvis' ears: wake word, recording and speech recognition (offline). """

# Libraries for the audio input
import time
import threading
import numpy as np
import sounddevice as sd

# Wake word (openWakeWord) and speech recognition (faster-whisper)
import openwakeword
from openwakeword.model import Model
from faster_whisper import WhisperModel

# ------------------------------------------------------------------
# SETTINGS (to adjust)
# ------------------------------------------------------------------
SAMPLE_RATE = 16000                            # Both openWakeWord and Whisper work at 16 kHz

WAKE_WORD_MODEL = "hey_jarvis"                 # Pre-trained model: you say "Hey Jarvis"
WAKE_THRESHOLD = 0.5                           # 0 to 1: lower = more sensitive but more false triggers

WHISPER_MODEL = "small"                        # "base" = faster, "small" = good balance, "medium" = more accurate but slower
WHISPER_DEVICE = "cpu"                         # "cpu" (simple) or "cuda" (needs extra NVIDIA libraries)
WHISPER_COMPUTE = "int8"                       # "int8" for cpu, "float16" for cuda
ALLOWED_LANGUAGES = ["fr", "en", "tr"]         # Whisper only chooses between these languages

VOICE_THRESHOLD = 0.02                         # Volume above which we consider that you are speaking (see show_levels())
SILENCE_SECONDS = 1.0                          # The command is over after this much silence
NO_SPEECH_TIMEOUT = 6.0                        # We give up if nothing is said within this delay
MAX_SECONDS = 15.0                             # Maximum length of a command
BEEP_ENABLED = True                            # Short beep when Jarvis starts listening

# ------------------------------------------------------------------
# LOADING
# ------------------------------------------------------------------
_wake_model = None
_whisper = None
_ready = threading.Event()                     # Becomes "true" when the models are loaded
_started = False                               # To know whether the loading has already been started

def load():
    """Loads the wake word model and Whisper once."""
    global _wake_model, _whisper
    try:
        openwakeword.utils.download_models()   # Only downloads what is missing (needs internet the first time)
    except Exception:
        pass                                   # Offline: we hope the models were already downloaded
    _wake_model = Model(wakeword_models=[WAKE_WORD_MODEL], inference_framework="onnx")
    _whisper = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    print("[Ears] Ready.")

# Loading in a thread: the program keeps running while the models load
def _load_thread():
    try:
        load()
    except Exception as e:
        print(f"[Ears] Loading failed : {e}")
    finally:
        _ready.set()

def load_in_background():
    """To call at the very beginning of the program (main.py)."""
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_load_thread, daemon=True).start()

# ------------------------------------------------------------------
# WAKE WORD
# ------------------------------------------------------------------
FRAME = 1280                                   # 80 ms of audio: the size openWakeWord expects

def wait_for_wake_word():
    """Blocks until the wake word is heard."""
    _ready.wait()
    if _wake_model is None:
        raise RuntimeError("Wake word model not loaded")
    if hasattr(_wake_model, "reset"):
        _wake_model.reset()                    # Forget the previous audio
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME) as stream:
        while True:
            frame, _ = stream.read(FRAME)
            scores = _wake_model.predict(frame.flatten())
            if max(scores.values()) >= WAKE_THRESHOLD:
                return

def beep():
    """Short beep to show that Jarvis is listening (we wait for it to end so the mic does not record it)."""
    if not BEEP_ENABLED:
        return
    t = np.linspace(0, 0.12, int(24000 * 0.12), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    sd.play(tone, 24000)
    sd.wait()

# ------------------------------------------------------------------
# RECORDING (stops by itself when you stop speaking)
# ------------------------------------------------------------------
def record_command():
    """Records until you stop speaking. Returns a float32 array, or None if nobody spoke."""
    block = int(SAMPLE_RATE * 0.1)             # Blocks of 100 ms
    chunks = []
    speech_started = False
    silence = 0.0
    start = time.time()
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block) as stream:
        while True:
            data, _ = stream.read(block)
            data = data.flatten()
            chunks.append(data)
            elapsed = time.time() - start

            if np.sqrt(np.mean(data ** 2)) > VOICE_THRESHOLD:     # Volume of this block
                speech_started = True
                silence = 0.0
            elif speech_started:
                silence += 0.1

            if speech_started and silence >= SILENCE_SECONDS:
                break
            if not speech_started and elapsed > NO_SPEECH_TIMEOUT:
                return None
            if elapsed > MAX_SECONDS:
                break
    return np.concatenate(chunks)

# ------------------------------------------------------------------
# SPEECH RECOGNITION
# ------------------------------------------------------------------
def transcribe(audio):
    """Turns the recorded audio into text. The language is chosen among ALLOWED_LANGUAGES."""
    language = None
    try:
        _, _, probabilities = _whisper.detect_language(audio)
        allowed = [(lang, p) for lang, p in probabilities if lang in ALLOWED_LANGUAGES]
        if allowed:
            language = max(allowed, key=lambda item: item[1])[0]
    except Exception:
        pass                                   # If the detection fails, Whisper decides on its own
    segments, info = _whisper.transcribe(
        audio,
        language=language,
        beam_size=1,                           # Faster
        vad_filter=True,                       # Ignores the silences (avoids invented sentences)
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text, (language or info.language)

# ------------------------------------------------------------------
# FULL CYCLE
# ------------------------------------------------------------------
def listen():
    """Waits for the wake word, records the command and turns it into text. Returns the text, or None."""
    wait_for_wake_word()
    beep()
    print("[Ears] Listening...")
    audio = record_command()
    if audio is None:
        print("[Ears] I heard nothing.")
        return None
    text, language = transcribe(audio)
    if text:
        print(f"You (voice, {language}) : {text}")
    return text or None

# Helper to adjust VOICE_THRESHOLD: speak, then stay silent, and compare the numbers
def show_levels(seconds=6):
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=1600) as stream:
        for _ in range(int(seconds * 10)):
            data, _ = stream.read(1600)
            print(f"volume : {np.sqrt(np.mean(data ** 2)):.4f}")