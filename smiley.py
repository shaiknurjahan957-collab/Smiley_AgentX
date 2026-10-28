#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          SMILEY AI VOICE ASSISTANT v2.0                      ║
║          Your Personal Jarvis — by Jafar Boss                ║
║          Python 3.10.11 | Windows | Production Ready         ║
╚══════════════════════════════════════════════════════════════╝

Wake word  : "Hey Smiley"
Inline cmd : "Hey Smiley open YouTube"
TTS engine : edge-tts  (Microsoft Neural female voice)
STT engine : Google Web Speech API (speech_recognition)

pip install:
    pip install SpeechRecognition edge-tts pygame pyautogui
                psutil pygetwindow pycaw comtypes pillow
"""

# ═══════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════
import asyncio
import os
import re
import sys
import time
import random
import tempfile
import threading
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

# ── Speech Recognition ────────────────────────────────────────
import speech_recognition as sr

# ── UI / Automation ───────────────────────────────────────────
import pyautogui
import psutil

# ── TTS ───────────────────────────────────────────────────────
import edge_tts
import pygame

# ── Window management (optional but preferred) ────────────────
try:
    import pygetwindow as gw
    HAS_GW = True
except ImportError:
    HAS_GW = False
    print("[WARN] pygetwindow not found — window switching disabled.")

# ── Volume control via pycaw (optional) ──────────────────────
try:
    from ctypes import cast, POINTER
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False
    print("[WARN] pycaw not found — using keyboard for volume.")

# ═══════════════════════════════════════════════════════════════
# GLOBAL CONFIG
# ═══════════════════════════════════════════════════════════════
WAKE_WORDS      = ["hey smiley", "hey smily", "hey smile", "ok smiley", "smiley"]
USER_NAME       = "Jafar boss"
VOICE           = "en-US-JennyNeural"   # Natural female neural voice
VOICE_RATE      = "+8%"                 # Slightly faster than default
VOICE_PITCH     = "+0Hz"
ENERGY_THRESH   = 300                   # Mic sensitivity
PAUSE_THRESH    = 0.75                  # Seconds of silence = end of speech
DYNAMIC_ENERGY  = True

pyautogui.FAILSAFE = True               # Move mouse to corner to abort
pyautogui.PAUSE    = 0.05              # Small pause between pyautogui calls

# ═══════════════════════════════════════════════════════════════
# TTS ENGINE  —  edge-tts  (non-blocking, threaded)
# ═══════════════════════════════════════════════════════════════
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

_tts_lock = threading.Lock()           # Prevent overlapping TTS calls


def _run_tts(text: str) -> None:
    """Generate audio with edge-tts and play it via pygame."""
    async def _gen(path: str) -> None:
        comm = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH)
        await comm.save(path)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        # Windows needs WindowsSelectorEventLoopPolicy for nested asyncio
        if sys.platform == "win32":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_gen(tmp_path))
            loop.close()
        else:
            asyncio.run(_gen(tmp_path))

        with _tts_lock:
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.04)
            pygame.mixer.music.unload()
    except Exception as e:
        print(f"[TTS-edge error] {e} — falling back to pyttsx3")
        try:
            import pyttsx3
            eng = pyttsx3.init()
            voices = eng.getProperty("voices")
            # Try to pick a female voice
            for v in voices:
                if "female" in v.name.lower() or "zira" in v.name.lower():
                    eng.setProperty("voice", v.id)
                    break
            eng.setProperty("rate", 175)
            eng.say(text)
            eng.runAndWait()
        except Exception as fe:
            print(f"[TTS-fallback error] {fe}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def speak(text: str, blocking: bool = True) -> None:
    """
    Speak `text` aloud.
    blocking=True  → caller waits until speech finishes (default for actions).
    blocking=False → fires and continues (use for quick acks).
    """
    print(f"\n  [Smiley] ▶  {text}")
    if blocking:
        _run_tts(text)
    else:
        t = threading.Thread(target=_run_tts, args=(text,), daemon=True)
        t.start()


# ═══════════════════════════════════════════════════════════════
# SPEECH RECOGNITION
# ═══════════════════════════════════════════════════════════════
_recognizer  = sr.Recognizer()
_recognizer.energy_threshold        = ENERGY_THRESH
_recognizer.pause_threshold         = PAUSE_THRESH
_recognizer.dynamic_energy_threshold = DYNAMIC_ENERGY
_mic = sr.Microphone()


def calibrate() -> None:
    """Calibrate mic for ambient noise once at startup."""
    print("[Smiley] Calibrating microphone …", end=" ", flush=True)
    with _mic as src:
        _recognizer.adjust_for_ambient_noise(src, duration=1.5)
    print(f"done  (threshold={_recognizer.energy_threshold:.0f})")


def listen(timeout: int = 10, phrase_limit: int = 8) -> str:
    """
    Listen for audio and return lowercase transcription.
    Returns empty string on silence / unrecognised / error.
    """
    try:
        with _mic as src:
            audio = _recognizer.listen(src, timeout=timeout,
                                       phrase_time_limit=phrase_limit)
        text = _recognizer.recognize_google(audio).lower().strip()
        print(f"  [Heard] ◉  {text}")
        return text
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"  [STT Request Error] {e}")
        return ""
    except Exception as e:
        print(f"  [Listen Error] {e}")
        return ""


def ask_and_listen(prompt: str, timeout: int = 8) -> str:
    """Speak a question, then listen for the answer."""
    speak(prompt)
    time.sleep(0.2)
    return listen(timeout=timeout)


# ═══════════════════════════════════════════════════════════════
# WAKE WORD EXTRACTION
# ═══════════════════════════════════════════════════════════════

def extract_command(text: str) -> str:
    """
    Strip the wake word from the beginning of `text` and
    return whatever follows as the command.
    """
    text = text.lower().strip()
    for wake in WAKE_WORDS:
        if wake in text:
            idx = text.find(wake)
            cmd = text[idx + len(wake):].strip(" ,.")
            return cmd
    return text


def is_wake_word(text: str) -> bool:
    return any(w in text for w in WAKE_WORDS)


# ═══════════════════════════════════════════════════════════════
# APPLICATION MAP  (Windows paths)
# ═══════════════════════════════════════════════════════════════
_USER = os.environ.get("USERNAME", "User")

APP_MAP: dict[str, str] = {
    # Browsers
    "chrome":           r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox":          r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge":             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge":   r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    # Dev tools
    "vs code":          rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vscode":           rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "pycharm":          r"C:\Program Files\JetBrains\PyCharm Community Edition\bin\pycharm64.exe",
    # Office
    "word":             r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":            r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint":       r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    # Built-ins
    "notepad":          "notepad.exe",
    "calculator":       "calc.exe",
    "paint":            "mspaint.exe",
    "cmd":              "cmd.exe",
    "command prompt":   "cmd.exe",
    "task manager":     "taskmgr.exe",
    "file explorer":    "explorer.exe",
    "explorer":         "explorer.exe",
    "snipping tool":    "snippingtool.exe",
    "control panel":    "control",
    "settings":         "ms-settings:",
    # Media
    "vlc":              r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "spotify":          rf"C:\Users\{_USER}\AppData\Roaming\Spotify\Spotify.exe",
    "media player":     "wmplayer.exe",
}

# Quick website aliases — opened directly in browser
WEBSITE_MAP: dict[str, str] = {
    "youtube":    "https://www.youtube.com",
    "google":     "https://www.google.com",
    "gmail":      "https://mail.google.com",
    "github":     "https://www.github.com",
    "linkedin":   "https://www.linkedin.com",
    "instagram":  "https://www.instagram.com",
    "twitter":    "https://www.twitter.com",
    "x":          "https://www.x.com",
    "whatsapp":   "https://web.whatsapp.com",
    "netflix":    "https://www.netflix.com",
    "chatgpt":    "https://chat.openai.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit":     "https://www.reddit.com",
}


# ═══════════════════════════════════════════════════════════════
# SYSTEM CONTROL MODULE
# ═══════════════════════════════════════════════════════════════

def open_app(name: str) -> bool:
    """
    Launch an application.
    Priority: APP_MAP → shell start → website alias.
    Returns True on success.
    """
    name = name.lower().strip()

    # ── 1. Exact match in APP_MAP ─────────────────────────────
    if name in APP_MAP:
        path = APP_MAP[name]
        try:
            if path.startswith("ms-"):
                subprocess.Popen(f'start "" "{path}"', shell=True)
            else:
                subprocess.Popen(f'start "" "{path}"', shell=True)
            return True
        except Exception as e:
            print(f"[open_app] {e}")

    # ── 2. Partial match in APP_MAP ───────────────────────────
    for key, path in APP_MAP.items():
        if name in key or key in name:
            try:
                subprocess.Popen(f'start "" "{path}"', shell=True)
                return True
            except Exception:
                pass

    # ── 3. Website alias ─────────────────────────────────────
    for key, url in WEBSITE_MAP.items():
        if key in name:
            webbrowser.open(url)
            return True

    # ── 4. Raw shell start (works for many .exe names) ───────
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True)
        return True
    except Exception:
        pass

    return False


def close_app(name: str) -> bool:
    """Kill process(es) by name substring."""
    name = name.lower().strip()
    killed = False
    for proc in psutil.process_iter(["name", "pid"]):
        pname = proc.info["name"].lower()
        if name in pname or pname.startswith(name[:6]):
            try:
                proc.kill()
                killed = True
                print(f"  [Killed] {proc.info['name']} (pid {proc.info['pid']})")
            except Exception:
                pass
    return killed


def switch_to_window(name: str) -> bool:
    """Bring a window with matching title to front."""
    if not HAS_GW:
        return False
    name = name.lower()
    try:
        for w in gw.getAllWindows():
            if name in w.title.lower() and w.visible:
                w.activate()
                time.sleep(0.4)
                return True
    except Exception as e:
        print(f"[switch_window] {e}")
    return False


# ── Volume ────────────────────────────────────────────────────

def set_volume(pct: int) -> None:
    """Set master volume to pct (0–100) using pycaw or nircmd."""
    pct = max(0, min(100, pct))
    if HAS_PYCAW:
        try:
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(pct / 100.0, None)
            return
        except Exception as e:
            print(f"[pycaw] {e}")
    # Fallback: nircmd (if installed) or key presses
    try:
        subprocess.run(
            f'nircmd.exe setsysvolume {int(pct * 655.35)}', shell=True, check=False
        )
    except Exception:
        pass


def mute_toggle() -> None:
    pyautogui.press("volumemute")


def volume_up(steps: int = 5) -> None:
    for _ in range(steps):
        pyautogui.press("volumeup")


def volume_down(steps: int = 5) -> None:
    for _ in range(steps):
        pyautogui.press("volumedown")


# ── Screen / Power ────────────────────────────────────────────

def lock_screen() -> None:
    subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)


def sleep_pc() -> None:
    subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)


def shutdown_pc() -> None:
    subprocess.run("shutdown /s /t 5", shell=True)


def restart_pc() -> None:
    subprocess.run("shutdown /r /t 5", shell=True)


def take_screenshot() -> str:
    desk = Path.home() / "Desktop"
    desk.mkdir(exist_ok=True)
    fname = desk / f"smiley_screenshot_{int(time.time())}.png"
    pyautogui.screenshot(str(fname))
    return str(fname)


# ═══════════════════════════════════════════════════════════════
# BROWSER CONTROL MODULE
# ═══════════════════════════════════════════════════════════════

def _open_url(url: str, wait: float = 2.5) -> None:
    webbrowser.open(url)
    time.sleep(wait)


def open_youtube(wait: float = 3.0) -> None:
    _open_url("https://www.youtube.com", wait)


def youtube_search(query: str) -> None:
    """Open YouTube search results for query."""
    q = query.strip().replace(" ", "+")
    _open_url(f"https://www.youtube.com/results?search_query={q}", wait=3.5)


def click_first_youtube_video() -> None:
    """
    After YouTube search, navigate to and click the first video.
    Strategy: Tab until we land on a video thumbnail link, then Enter.
    """
    time.sleep(1.5)
    # Dismiss any cookie / overlay
    pyautogui.press("escape")
    time.sleep(0.3)
    # Tab past the search bar and filters to reach first result
    for _ in range(6):
        pyautogui.press("tab")
        time.sleep(0.12)
    pyautogui.press("enter")
    time.sleep(3)


def yt_play_pause() -> None:
    """Toggle play/pause — YouTube shortcut 'k'."""
    pyautogui.press("k")


def yt_mute() -> None:
    pyautogui.press("m")


def yt_fullscreen() -> None:
    pyautogui.press("f")


def yt_skip_forward(sec: int = 10) -> None:
    """Skip forward by pressing 'l' (5 s each)."""
    presses = max(1, sec // 5)
    for _ in range(presses):
        pyautogui.press("l")
        time.sleep(0.1)


def yt_skip_backward(sec: int = 10) -> None:
    presses = max(1, sec // 5)
    for _ in range(presses):
        pyautogui.press("j")
        time.sleep(0.1)


def scroll_down(clicks: int = 4) -> None:
    pyautogui.scroll(-clicks * 80)


def scroll_up(clicks: int = 4) -> None:
    pyautogui.scroll(clicks * 80)


def google_search(query: str) -> None:
    q = query.strip().replace(" ", "+")
    _open_url(f"https://www.google.com/search?q={q}", wait=2)


def open_website(url: str) -> None:
    if not url.startswith("http"):
        url = "https://" + url
    _open_url(url)


# ── Browser tab shortcuts ─────────────────────────────────────

def new_tab()    : pyautogui.hotkey("ctrl", "t")
def close_tab()  : pyautogui.hotkey("ctrl", "w")
def next_tab()   : pyautogui.hotkey("ctrl", "tab")
def prev_tab()   : pyautogui.hotkey("ctrl", "shift", "tab")
def reload_page(): pyautogui.press("f5")
def go_back()    : pyautogui.hotkey("alt", "left")
def go_forward() : pyautogui.hotkey("alt", "right")


def navigate_to(url: str) -> None:
    """Focus address bar and navigate."""
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.25)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.typewrite(url, interval=0.04)
    pyautogui.press("enter")
    time.sleep(2.5)


# ═══════════════════════════════════════════════════════════════
# WHATSAPP AUTOMATION MODULE
# ═══════════════════════════════════════════════════════════════

def send_whatsapp(contact: str, message: str) -> None:
    """
    Send a WhatsApp Web message to `contact`.
    Assumes Chrome / default browser is already logged in to WA Web.
    """
    speak(f"Opening WhatsApp Web {USER_NAME}")
    _open_url("https://web.whatsapp.com", wait=7)  # WA Web can be slow

    # ── Search for contact ────────────────────────────────────
    # Keyboard shortcut: Ctrl+F opens the new conversation / search box in WA Web
    pyautogui.hotkey("ctrl", "f")
    time.sleep(1.2)
    pyautogui.typewrite(contact, interval=0.06)
    time.sleep(2.0)

    # Select first result from search list (Down arrow + Enter)
    pyautogui.press("down")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.2)

    # ── Type and send message ─────────────────────────────────
    # Click on the message input area (lower portion of chat pane)
    sw, sh = pyautogui.size()
    # WA Web message box is roughly at (65% width, 95% height)
    pyautogui.click(int(sw * 0.65), int(sh * 0.93))
    time.sleep(0.5)

    # Type message character by character (handles spaces correctly)
    pyautogui.write(message, interval=0.04)
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_time() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def get_date() -> str:
    return datetime.now().strftime("%A, %B %d, %Y")


def type_text(text: str) -> None:
    pyautogui.write(text, interval=0.03)


def _number_from(text: str, default: int = 3) -> int:
    """Extract first integer found in text, or return default."""
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else default


JOKES = [
    f"Why did the programmer quit his job? Because he didn't get arrays, {USER_NAME}!",
    f"Why do programmers prefer dark mode? Because light attracts bugs, {USER_NAME}!",
    f"What do you call a fish with no eyes? A fsh, {USER_NAME}!",
    f"I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads, {USER_NAME}!",
    f"Why was the math book sad? Because it had too many problems, {USER_NAME}!",
]


# ═══════════════════════════════════════════════════════════════
# COMMAND PROCESSOR  —  Heart of Smiley
# ═══════════════════════════════════════════════════════════════

def process(cmd: str) -> None:
    """
    Receives a stripped command string (wake word already removed).
    Routes to the appropriate handler, speaks confirmation, then acts.
    """
    if not cmd:
        speak(f"Yes {USER_NAME}, how can I help you?")
        return

    c = cmd.lower().strip()

    # ─────────────────────────────────────────────────────────
    # GREETINGS / SMALL TALK
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(hello|hi|hey|good morning|good afternoon|good evening)\b", c):
        hour = datetime.now().hour
        if hour < 12:
            greet = "Good morning"
        elif hour < 17:
            greet = "Good afternoon"
        else:
            greet = "Good evening"
        speak(f"{greet} {USER_NAME}! How can I assist you today?")
        return

    if re.search(r"\b(how are you|are you okay|you good)\b", c):
        speak(f"I'm running smoothly and ready to help you, {USER_NAME}!")
        return

    if re.search(r"\b(what is your name|who are you)\b", c):
        speak(f"I'm Smiley, your personal AI assistant, {USER_NAME}!")
        return

    if re.search(r"\b(joke|make me laugh|tell me something funny)\b", c):
        speak(random.choice(JOKES))
        return

    # ─────────────────────────────────────────────────────────
    # TIME & DATE
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(time)\b", c):
        speak(f"The current time is {get_time()}, {USER_NAME}")
        return

    if re.search(r"\b(date|today|day)\b", c):
        speak(f"Today is {get_date()}, {USER_NAME}")
        return

    # ─────────────────────────────────────────────────────────
    # YOUTUBE
    # ─────────────────────────────────────────────────────────
    if "youtube" in c:
        # play / search on YouTube
        if re.search(r"\b(play|search|find|watch)\b", c):
            query = re.sub(
                r"\b(play|search|find|watch|on|in|youtube|for|me|a|the|some)\b", "", c
            ).strip(" ,.")
            if query:
                speak(f"Searching YouTube for {query}, {USER_NAME}")
                youtube_search(query)
                speak(f"Opening the first video {USER_NAME}")
                click_first_youtube_video()
            else:
                speak(f"Opening YouTube {USER_NAME}")
                open_youtube()
        elif "open" in c or "go to" in c:
            speak(f"Opening YouTube {USER_NAME}")
            open_youtube()
        elif re.search(r"\b(pause|stop)\b", c):
            speak(f"Pausing the video {USER_NAME}")
            yt_play_pause()
        elif re.search(r"\b(resume|continue|unpause)\b", c):
            speak(f"Resuming the video {USER_NAME}")
            yt_play_pause()
        elif "mute" in c:
            speak(f"Muting the video {USER_NAME}")
            yt_mute()
        elif "fullscreen" in c or "full screen" in c:
            speak(f"Going fullscreen {USER_NAME}")
            yt_fullscreen()
        elif re.search(r"\b(forward|skip ahead)\b", c):
            secs = _number_from(c, 10)
            speak(f"Skipping forward {secs} seconds {USER_NAME}")
            yt_skip_forward(secs)
        elif re.search(r"\b(backward|rewind|go back)\b", c):
            secs = _number_from(c, 10)
            speak(f"Rewinding {secs} seconds {USER_NAME}")
            yt_skip_backward(secs)
        return

    # Standalone play / pause (not YouTube-specific)
    if re.match(r"^(play|pause|resume|stop playing)$", c):
        action = "Pausing" if "pause" in c or "stop" in c else "Playing"
        speak(f"{action} {USER_NAME}")
        yt_play_pause()
        return

    # ─────────────────────────────────────────────────────────
    # OPEN  (apps + websites)
    # ─────────────────────────────────────────────────────────
    if c.startswith("open ") or re.match(r"launch|start ", c):
        target = re.sub(r"^(open|launch|start)\s+", "", c).strip()

        # Website aliases first
        for key, url in WEBSITE_MAP.items():
            if key in target:
                speak(f"Opening {key.title()} {USER_NAME}")
                _open_url(url)
                return

        # Then apps
        speak(f"Opening {target} {USER_NAME}")
        if not open_app(target):
            speak(f"I couldn't find {target}, {USER_NAME}. Please check if it's installed.")
        return

    # ─────────────────────────────────────────────────────────
    # CLOSE
    # ─────────────────────────────────────────────────────────
    if c.startswith("close ") or c.startswith("kill "):
        target = re.sub(r"^(close|kill)\s+", "", c).strip()
        speak(f"Closing {target} {USER_NAME}")
        if not close_app(target):
            pyautogui.hotkey("alt", "f4")
        return

    # ─────────────────────────────────────────────────────────
    # SWITCH WINDOW
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(switch to|go to|open window|bring up)\b", c):
        target = re.sub(r"\b(switch to|go to|open window|bring up)\b", "", c).strip()
        speak(f"Switching to {target} {USER_NAME}")
        if not switch_to_window(target):
            speak(f"I couldn't find a {target} window, {USER_NAME}")
        return

    # ─────────────────────────────────────────────────────────
    # SEARCH (Google)
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(search|google|look up|find)\b", c) and "youtube" not in c:
        query = re.sub(r"\b(search|google|look up|find|for|on the internet|online|me)\b", "", c).strip()
        if query:
            speak(f"Searching Google for {query}, {USER_NAME}")
            google_search(query)
        return

    # ─────────────────────────────────────────────────────────
    # WHATSAPP
    # ─────────────────────────────────────────────────────────
    if "whatsapp" in c or ("send" in c and "message" in c):
        contact = ask_and_listen(f"Who should I send the message to, {USER_NAME}?")
        if not contact:
            speak(f"I didn't catch the contact name, {USER_NAME}")
            return
        message = ask_and_listen(f"What message should I send to {contact}, {USER_NAME}?")
        if not message:
            speak(f"I didn't catch the message, {USER_NAME}")
            return
        speak(f"Sending message to {contact}, {USER_NAME}")
        send_whatsapp(contact, message)
        speak(f"Message sent to {contact}, {USER_NAME}!")
        return

    # ─────────────────────────────────────────────────────────
    # SCROLL
    # ─────────────────────────────────────────────────────────
    if "scroll down" in c:
        n = _number_from(c, 4)
        speak(f"Scrolling down {USER_NAME}")
        scroll_down(n)
        return

    if "scroll up" in c:
        n = _number_from(c, 4)
        speak(f"Scrolling up {USER_NAME}")
        scroll_up(n)
        return

    # ─────────────────────────────────────────────────────────
    # VOLUME
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(volume up|increase volume|turn up|louder)\b", c):
        n = _number_from(c, 5)
        speak(f"Increasing volume {USER_NAME}")
        volume_up(n)
        return

    if re.search(r"\b(volume down|decrease volume|turn down|quieter)\b", c):
        n = _number_from(c, 5)
        speak(f"Decreasing volume {USER_NAME}")
        volume_down(n)
        return

    if re.search(r"\b(mute|silence|quiet)\b", c) and "youtube" not in c:
        speak(f"Muting audio {USER_NAME}")
        mute_toggle()
        return

    if "unmute" in c:
        speak(f"Unmuting audio {USER_NAME}")
        mute_toggle()
        return

    if re.search(r"\bset volume\b", c):
        pct = _number_from(c, 50)
        speak(f"Setting volume to {pct} percent {USER_NAME}")
        set_volume(pct)
        return

    # ─────────────────────────────────────────────────────────
    # SYSTEM POWER / SCREEN
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(lock screen|lock computer|lock pc)\b", c):
        speak(f"Locking your screen {USER_NAME}")
        time.sleep(1)
        lock_screen()
        return

    if re.search(r"\b(sleep|hibernate)\b", c) and re.search(r"\b(computer|pc|system|laptop)\b", c):
        speak(f"Putting your computer to sleep {USER_NAME}")
        time.sleep(2)
        sleep_pc()
        return

    if re.search(r"\b(shutdown|shut down|turn off)\b", c) and re.search(r"\b(computer|pc|system|laptop)\b", c):
        conf = ask_and_listen(f"Are you sure you want to shut down, {USER_NAME}? Say yes to confirm.")
        if "yes" in conf:
            speak(f"Shutting down in 5 seconds {USER_NAME}")
            shutdown_pc()
        else:
            speak(f"Shutdown cancelled {USER_NAME}")
        return

    if re.search(r"\b(restart|reboot)\b", c):
        conf = ask_and_listen(f"Are you sure you want to restart, {USER_NAME}? Say yes to confirm.")
        if "yes" in conf:
            speak(f"Restarting in 5 seconds {USER_NAME}")
            restart_pc()
        else:
            speak(f"Restart cancelled {USER_NAME}")
        return

    if re.search(r"\b(screenshot|capture screen|screen capture)\b", c):
        speak(f"Taking a screenshot {USER_NAME}")
        path = take_screenshot()
        speak(f"Screenshot saved to your desktop {USER_NAME}")
        return

    # ─────────────────────────────────────────────────────────
    # BROWSER TABS & NAVIGATION
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(new tab|open tab)\b", c):
        speak(f"Opening new tab {USER_NAME}")
        new_tab()
        return

    if re.search(r"\b(close tab)\b", c):
        speak(f"Closing tab {USER_NAME}")
        close_tab()
        return

    if re.search(r"\b(next tab)\b", c):
        speak(f"Next tab {USER_NAME}")
        next_tab()
        return

    if re.search(r"\b(previous tab|last tab|back tab)\b", c):
        speak(f"Previous tab {USER_NAME}")
        prev_tab()
        return

    if re.search(r"\b(refresh|reload)\b", c):
        speak(f"Refreshing {USER_NAME}")
        reload_page()
        return

    if re.search(r"\b(go back|back)\b", c) and "volume" not in c:
        speak(f"Going back {USER_NAME}")
        go_back()
        return

    if re.search(r"\b(go forward|forward)\b", c):
        speak(f"Going forward {USER_NAME}")
        go_forward()
        return

    if re.search(r"\b(navigate to|go to website)\b", c):
        url = re.sub(r"\b(navigate to|go to website)\b", "", c).strip()
        speak(f"Navigating to {url}, {USER_NAME}")
        navigate_to(url)
        return

    # ─────────────────────────────────────────────────────────
    # KEYBOARD SHORTCUTS
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(copy)\b", c):
        speak(f"Copying {USER_NAME}")
        pyautogui.hotkey("ctrl", "c")
        return

    if re.search(r"\b(paste)\b", c):
        speak(f"Pasting {USER_NAME}")
        pyautogui.hotkey("ctrl", "v")
        return

    if re.search(r"\b(cut)\b", c):
        speak(f"Cutting {USER_NAME}")
        pyautogui.hotkey("ctrl", "x")
        return

    if re.search(r"\b(undo)\b", c):
        speak(f"Undoing {USER_NAME}")
        pyautogui.hotkey("ctrl", "z")
        return

    if re.search(r"\b(redo)\b", c):
        speak(f"Redoing {USER_NAME}")
        pyautogui.hotkey("ctrl", "y")
        return

    if re.search(r"\b(select all)\b", c):
        speak(f"Selecting all {USER_NAME}")
        pyautogui.hotkey("ctrl", "a")
        return

    if re.search(r"\b(save)\b", c):
        speak(f"Saving {USER_NAME}")
        pyautogui.hotkey("ctrl", "s")
        return

    if re.search(r"\b(minimize|minimise)\b", c):
        speak(f"Minimizing window {USER_NAME}")
        pyautogui.hotkey("win", "down")
        return

    if re.search(r"\b(maximize|maximise)\b", c):
        speak(f"Maximizing window {USER_NAME}")
        pyautogui.hotkey("win", "up")
        return

    if re.search(r"\b(hide all|show desktop|desktop)\b", c):
        speak(f"Showing desktop {USER_NAME}")
        pyautogui.hotkey("win", "d")
        return

    if re.search(r"\b(alt tab|switch window|task switcher)\b", c):
        speak(f"Switching window {USER_NAME}")
        pyautogui.hotkey("alt", "tab")
        return

    # ─────────────────────────────────────────────────────────
    # TYPE TEXT
    # ─────────────────────────────────────────────────────────
    if c.startswith("type "):
        text = c[5:].strip()
        speak(f"Typing for you {USER_NAME}")
        type_text(text)
        return

    if c.startswith("press "):
        key = c[6:].strip()
        speak(f"Pressing {key} {USER_NAME}")
        pyautogui.press(key)
        return

    # ─────────────────────────────────────────────────────────
    # STOP SMILEY
    # ─────────────────────────────────────────────────────────
    if re.search(r"\b(stop smiley|exit smiley|quit smiley|goodbye smiley|bye smiley|shutdown smiley|turn off smiley)\b", c):
        speak(f"Goodbye {USER_NAME}! Have a wonderful day. See you soon!")
        sys.exit(0)

    # ─────────────────────────────────────────────────────────
    # FALLBACK
    # ─────────────────────────────────────────────────────────
    speak(
        f"I'm sorry {USER_NAME}, I don't know how to do that yet. "
        f"Could you try rephrasing, or ask me something else?"
    )


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    print("""
╔══════════════════════════════════════════════════════════════╗
║          SMILEY AI VOICE ASSISTANT v2.0                      ║
║          Say  "Hey Smiley <command>"  to get started         ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Set event loop policy on Windows (required for edge-tts)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    calibrate()

    speak(
        f"Hello {USER_NAME}! "
        f"I'm Smiley, your personal AI assistant. "
        f"Just say Hey Smiley followed by your command, and I'll take care of it."
    )

    print("\n  [Listening for wake word …]\n")

    while True:
        try:
            # ── Continuous listening ──────────────────────────────
            raw = listen(timeout=30, phrase_limit=8)

            if not raw:
                continue

            # ── Wake word gate ────────────────────────────────────
            if not is_wake_word(raw):
                continue

            # ── Acknowledge immediately (non-blocking) ────────────
            speak(f"Yes {USER_NAME}", blocking=False)

            # ── Extract inline command ────────────────────────────
            cmd = extract_command(raw)

            if cmd:
                # Brief pause so "Yes Jafar boss" finishes before
                # the action voice line starts
                time.sleep(0.6)
                process(cmd)
            else:
                # Wake word only — wait for follow-up command
                speak(f"How can I help you, {USER_NAME}?")
                followup = listen(timeout=8)
                if followup:
                    process(followup)

            print("\n  [Listening for wake word …]\n")

        except KeyboardInterrupt:
            speak(f"Goodbye {USER_NAME}!")
            print("\n[Exited by user]")
            break
        except Exception as e:
            print(f"  [Main loop error] {e}")
            time.sleep(0.5)
            continue


if __name__ == "__main__":
    main()
