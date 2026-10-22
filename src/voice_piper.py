""" Jarvis voice: OFFLINE speech synthesis with Piper + "Jarvis" effect added with pedalboard """


# Libraries for the audio output + Regex
import numpy as np
import sounddevice as sd
import re                                      # Regex

# Libraries for background loading and parallel playback
import threading
import queue
from concurrent.futures import ThreadPoolExecutor

# Library to access file paths
from pathlib import Path

# Voice engine (Piper), audio effects (pedalboard) and language detection (lingua)
from piper import PiperVoice
from pedalboard import Pedalboard, HighpassFilter, LowpassFilter, Chorus, Reverb
from lingua import Language, LanguageDetectorBuilder

# ------------------------------------------------------------------
# SETTINGS (to adjust by ear)
# ------------------------------------------------------------------
VOICES_DIR = Path(__file__).parent.parent / "piper_voices"    # Folder containing the .onnx and .onnx.json files
DEFAULT_LANGUAGE = "fr"                                # Language used when the detection fails

# Name of the Piper voice for each language (adapt to the voices you downloaded)
VOICES = {
    "fr": "fr_FR-tom-medium",
    "en": "jarvis-medium",
    "tr": "tr_TR-dfki-medium"
}

# "Jarvis" effect: set EFFECTS_ENABLED = False to hear the raw voice
EFFECTS_ENABLED = True
CHORUS_MIX = 0.25                              # 0 = no voice doubling, 0.5 = very noticeable
REVERB_WET = 0.12                              # Amount of echo/reverb (0 to 0.3 recommended)
HIGHPASS_HZ = 150                              # Removes the bass (voice less "boomy")
LOWPASS_HZ = 7000                              # Removes the treble (voice a bit more "radio")

# ------------------------------------------------------------------
# SHARED VARIABLES
# ------------------------------------------------------------------
_voices = {}                                   # Loaded voices: {"fr": PiperVoice, ...}
_ready = threading.Event()                     # Becomes "true" when the voices are loaded
_started = False                               # To know whether the loading has already been started

# Automatic detection of the text language (limited to fr / en / tr)
_detector = LanguageDetectorBuilder.from_languages(Language.FRENCH, Language.ENGLISH, Language.TURKISH).build()
_CODES = {Language.FRENCH: "fr", Language.ENGLISH: "en", Language.TURKISH: "tr"}

# Effects chain of the "Jarvis" effect
_effects = Pedalboard([
    HighpassFilter(cutoff_frequency_hz=HIGHPASS_HZ),
    LowpassFilter(cutoff_frequency_hz=LOWPASS_HZ),
    Chorus(rate_hz=1.2, depth=0.25, centre_delay_ms=7.0, feedback=0.0, mix=CHORUS_MIX),
    Reverb(room_size=0.12, damping=0.6, wet_level=REVERB_WET, dry_level=0.9),
])

def detect_language(text, default=DEFAULT_LANGUAGE):
    """Detects the language of the text (fr / en / tr), otherwise returns the default language."""
    return _CODES.get(_detector.detect_language_of(text), default)

# ------------------------------------------------------------------
# LOADING
# ------------------------------------------------------------------
def _synthesize(voice, sentence):
    """Turns a sentence into sound (float32 array). Handles both versions of the Piper API."""
    if hasattr(voice, "synthesize_stream_raw"):            # Older versions of Piper
        raw_bytes = b"".join(voice.synthesize_stream_raw(sentence))
        return np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    pieces = []                                            # Recent versions of Piper
    for chunk in voice.synthesize(sentence):
        if hasattr(chunk, "audio_float_array"):
            pieces.append(np.asarray(chunk.audio_float_array, dtype=np.float32))
        else:
            pieces.append(np.asarray(chunk.audio_int16_array, dtype=np.float32) / 32768.0)
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)

def load():
    """Loads the Piper voices once (fast, a few seconds)."""
    for language, name in VOICES.items():
        path = VOICES_DIR / f"{name}.onnx"
        if not path.exists():
            print(f"[Voice] File not found : {path.name} (language '{language}' ignored)")
            continue
        _voices[language] = PiperVoice.load(str(path))
        _synthesize(_voices[language], "Ready.")           # Warm-up
    print(f"[Voice] Ready ({', '.join(_voices) or 'no voice'}).")

# Loading in a thread: the program keeps running while the voices load
def _load_thread():
    try:
        load()
    except Exception as e:
        print(f"[Voice] Loading failed : {e}")
    finally:
        _ready.set()                           # In any case we release the wait (even if the loading failed)

def load_in_background():
    """To call at the very beginning of the program (main.py), before starting Ollama."""
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_load_thread, daemon=True).start()

# ------------------------------------------------------------------
# TEXT
# ------------------------------------------------------------------
# Use of Regex
def _clean_text(text):
    text = re.sub(r"[*_#`~]", "", text)                    # leftover markdown
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)    # emojis
    return re.sub(r"\s+", " ", text).strip()

# Splits the text into sentences (the period is kept: Piper uses it for intonation and does not pronounce it)
def _split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]

# Applies the "Jarvis" effect to a sentence
def _apply_effects(audio, sample_rate):
    if not EFFECTS_ENABLED or audio.size == 0:
        return audio
    silence = np.zeros(int(sample_rate * 0.25), dtype=np.float32)  # Leaves room for the reverb tail
    output = _effects(np.concatenate([audio, silence]).reshape(1, -1), sample_rate)
    return output.reshape(-1)

# ------------------------------------------------------------------
# SPEECH
# ------------------------------------------------------------------
# Function that turns the text into speech (TTS)
def speak(text, language=DEFAULT_LANGUAGE):
    """ Turns the text into speech directly (without reading/writing a .wav file).
    The language is detected automatically from the text."""
    if not text:
        return
    text = _clean_text(text)
    if not text:
        return
    language = detect_language(text, language)

    # If the loading was not started at launch, we start it now, then wait until it is ready
    if not _started:
        load_in_background()
    _ready.wait()

    voice = _voices.get(language) or _voices.get(DEFAULT_LANGUAGE)     # If the voice of the language is missing, use the default language
    if voice is None:
        print("[Voice] No voice available.")
        return
    sample_rate = voice.config.sample_rate
    audio_queue = queue.Queue()                # Queue between the generation and the playback

    # Thread 1 (producer): generates each sentence, adds the effect, and puts it in the queue
    def producer():
        try:
            for sentence in _split_sentences(text):
                audio = _apply_effects(_synthesize(voice, sentence), sample_rate)
                peak = np.max(np.abs(audio)) if audio.size else 0
                if peak > 0:
                    audio = audio / peak * 0.9         # constant volume from one sentence to the next
                audio_queue.put(audio.astype(np.float32))
        except Exception as e:
            print(f"[Voice] Error : {e}")
        finally:
            audio_queue.put(None)              # End signal

    threading.Thread(target=producer, daemon=True).start()

    # Main thread (consumer): plays the sentences as soon as they are ready
    try:
        with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
            while (chunk := audio_queue.get()) is not None:
                stream.write(chunk.reshape(-1, 1))
    except Exception as e:
        print(f"[Voice] Playback error : {e}")

# A single "player": sentences follow each other without overlapping, and the program is not blocked
_player = ThreadPoolExecutor(max_workers=1)

def speak_in_background(text, language=DEFAULT_LANGUAGE):
    """Runs speak() in the background (the text is displayed right away, the voice follows)."""
    return _player.submit(speak, text, language)

def wait_until_done():
    """Waits until Jarvis has finished speaking (to call before listening to the microphone)."""
    _player.submit(lambda: None).result()