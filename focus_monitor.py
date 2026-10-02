"""
Personal Focus Monitor with Cat Board Overlay
Runs in the background (no camera window).
A cute cat holding a message board pops up whenever you lose focus or get sleepy.
Integrates with Windows System Tray and Windows Startup.
"""
import sys
import os
import time
import argparse
import threading
from datetime import datetime

import cv2
import numpy as np
import mediapipe as mp
from PIL import Image

import ctypes
from cat_popup import CatPopup
import autostart

# ---------------- Keyboard / User Activity Detection ----------------
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

def get_idle_seconds():
    """Returns seconds since last keyboard keystroke or mouse movement."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return millis / 1000.0
    except Exception:
        pass
    return 999.0

# ---------------- Settings ----------------
AWAY_WARN_S = 4.5       # looking away this long -> warning (relaxed so glancing at screen edges is ok)
AWAY_STRONG_S = 10.0    # ...and a stronger alert
EYES_CLOSED_S = 1.8     # eyes genuinely closed this long -> sleepy (no false alarms while reading or thinking!)
NO_FACE_S = 4.0         # face missing this long -> alert
YAWN_S = 1.6            # mouth wide open this long -> yawn
CALIB_FRAMES = 50       # frames used to learn your "normal" pose

YAW_TOL, PITCH_TOL, GAZE_TOL = 0.22, 0.20, 0.28  # Generous margins so reading screen doesn't trigger 'away'
EAR_RATIO_CLOSED = 0.65 # eyes truly shut if EAR < 65% of normal baseline
EAR_ABSOLUTE_CEILING = 0.16 # strict ceiling: only closed eyes drop below 0.16
MAR_YAWN = 0.62

# Cooldown between repeated alerts of the same kind (relaxed so it doesn't nag)
ALERT_COOLDOWNS = {
    "sleepy": 10.0,
    "away": 10.0,
    "away_strong": 12.0,
    "yawn": 12.0,
    "noface": 8.0,
}

RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]

# ---------------- Global State ----------------
_last_alert = {}
_tts_lock = threading.Lock()
_popup = None
_running = True
_recalibrate_requested = False
_current_state = "STARTING"
_sound_enabled = True


# ---------------- Audio & Visual Alerts ----------------
def _speak(msg):
    if not _sound_enabled:
        return
    if not _tts_lock.acquire(blocking=False):
        return
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(msg)
        engine.runAndWait()
    except Exception:
        pass
    finally:
        _tts_lock.release()


def trigger_alert(kind, cat_text, spoken_text, duration=4.0):
    now = time.time()
    cooldown = ALERT_COOLDOWNS.get(kind, 6.0)
    if now - _last_alert.get(kind, 0) >= cooldown:
        _last_alert[kind] = now
        print(f"[ALERT: {kind}] {spoken_text}")
        if _popup is not None:
            _popup.show(cat_text, duration=duration)
        if spoken_text:
            threading.Thread(target=_speak, args=(spoken_text,), daemon=True).start()


# ---------------- Feature Extraction ----------------
def _pts(lm, idx, w, h):
    return np.array([[lm[i].x * w, lm[i].y * h] for i in idx])


def _ear(e):
    d = np.linalg.norm
    return (d(e[1] - e[5]) + d(e[2] - e[4])) / (2 * d(e[0] - e[3]) + 1e-6)


def features(lm, w, h):
    re, le = _pts(lm, RIGHT_EYE, w, h), _pts(lm, LEFT_EYE, w, h)
    ear = (_ear(re) + _ear(le)) / 2

    p = lambda i: np.array([lm[i].x * w, lm[i].y * h])
    mar = np.linalg.norm(p(13) - p(14)) / (np.linalg.norm(p(78) - p(308)) + 1e-6)

    nose, lcheek, rcheek = p(1), p(234), p(454)
    top, chin = p(10), p(152)
    yaw = (nose[0] - lcheek[0]) / (rcheek[0] - lcheek[0] + 1e-6)
    pitch = (nose[1] - top[1]) / (chin[1] - top[1] + 1e-6)

    gr = (p(468)[0] - p(33)[0]) / (p(133)[0] - p(33)[0] + 1e-6)
    gl = (p(473)[0] - p(362)[0]) / (p(263)[0] - p(362)[0] + 1e-6)
    gaze = (gr + gl) / 2
    return dict(ear=ear, mar=mar, yaw=yaw, pitch=pitch, gaze=gaze)


# ---------------- System Tray ----------------
def setup_tray():
    try:
        import pystray
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base_dir, "cat_icon.ico")
        if os.path.exists(ico_path):
            img = Image.open(ico_path)
        else:
            img = Image.new("RGBA", (32, 32), (255, 160, 50, 255))

        def on_recalib(icon, item):
            global _recalibrate_requested
            _recalibrate_requested = True

        def on_test(icon, item):
            if _popup:
                _popup.show("Focus!\nKeep going! 🐾", duration=3.5)

        def on_toggle_sound(icon, item):
            global _sound_enabled
            _sound_enabled = not _sound_enabled

        def on_toggle_startup(icon, item):
            if autostart.is_autostart_installed():
                autostart.remove_autostart()
            else:
                autostart.install_autostart()

        def on_open_report(icon, item):
            report_file = os.path.join(base_dir, "focus_report.txt")
            if not os.path.exists(report_file):
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write("Focus Monitor is running.\n")
            os.startfile(report_file)

        def on_exit(icon, item):
            global _running
            _running = False
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Focus Monitor (Running)", None, enabled=False),
            pystray.MenuItem(lambda text: f"Status: {_current_state}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Recalibrate Normal Pose", on_recalib),
            pystray.MenuItem("Test Cat Popup", on_test),
            pystray.MenuItem("Sound / TTS Alerts", on_toggle_sound, checked=lambda item: _sound_enabled),
            pystray.MenuItem("Start with Windows", on_toggle_startup, checked=lambda item: autostart.is_autostart_installed()),
            pystray.MenuItem("View Focus Report", on_open_report),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit),
        )

        icon = pystray.Icon("FocusMonitor", img, "Focus Monitor (Cat Alert)", menu=menu)
        icon.run_detached()
        return icon
    except Exception as e:
        print("[Tray Warning] Could not start system tray icon:", e)
        return None


# ---------------- Main Loop ----------------
def run_monitor(show_preview=False):
    global _running, _recalibrate_requested, _current_state, _popup

    # Initialize the cute Cat Popup overlay
    _popup = CatPopup()
    _popup.show("Focus Monitor\nis Ready! 🐾", duration=3.0)

    # Initialize System Tray
    tray_icon = setup_tray()

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1, refine_landmarks=True,
        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    cap = cv2.VideoCapture(0)

    base, calib = None, []
    stats = {"FOCUSED": 0.0, "DISTRACTED": 0.0, "SLEEPY": 0.0, "NO FACE": 0.0}
    distractions = yawns = 0
    longest_focus = cur_focus = 0.0
    away_t = closed_t = noface_t = yawn_t = 0.0
    was_distracted = yawned = False
    start = prev = time.time()

    calib_announced = False

    while _running:
        if not cap.isOpened():
            print("[Webcam] Attempting to connect to camera...")
            cap.open(0)
            if not cap.isOpened():
                time.sleep(2.0)
                continue

        ok, frame = cap.read()
        if not ok:
            # Handle laptop sleep or temporary camera disconnect
            time.sleep(1.0)
            continue

        if _recalibrate_requested:
            base, calib = None, []
            calib_announced = False
            _recalibrate_requested = False
            _popup.show("Calibrating...\nLook at screen 👀", duration=3.0)

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        now = time.time()
        dt, prev = now - prev, now

        res = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        state = "FOCUSED"

        if not res.multi_face_landmarks:
            noface_t += dt
            away_t = closed_t = yawn_t = 0
            if noface_t >= NO_FACE_S:
                state = "NO FACE"
                trigger_alert(
                    kind="noface",
                    cat_text="Where are\nyou? 🐾\nCome back!",
                    spoken_text="Come back!",
                    duration=4.0
                )
        else:
            noface_t = 0
            f = features(res.multi_face_landmarks[0].landmark, w, h)

            if base is None:
                state = "CALIBRATING"
                if not calib_announced:
                    _popup.show("Calibrating...\nLook at screen 👀", duration=3.0)
                    calib_announced = True
                if f["ear"] > 0.18:
                    calib.append(f)
                if len(calib) >= CALIB_FRAMES:
                    base = {k: float(np.median([c[k] for c in calib])) for k in f}
                    start = prev = time.time()
                    _popup.show("All set! ✨\nStay focused!", duration=2.5)
            else:
                # Check if user is actively typing or using mouse
                is_active_input = get_idle_seconds() < 2.5

                # Check if head is tilted down looking at keyboard / desk
                looking_down_at_keyboard = (f["pitch"] - base["pitch"]) > 0.08

                looking_away = (abs(f["yaw"] - base["yaw"]) > YAW_TOL
                                or (f["pitch"] - base["pitch"] < -PITCH_TOL)
                                or (f["pitch"] - base["pitch"] > PITCH_TOL + 0.12)
                                or abs(f["gaze"] - base["gaze"]) > GAZE_TOL)

                # Only consider eyes closed when NOT typing and NOT looking down at keyboard
                ear_val = f["ear"]
                eyes_closed = (not looking_down_at_keyboard) and (not is_active_input) and (
                    (ear_val < base["ear"] * EAR_RATIO_CLOSED) or (ear_val < EAR_ABSOLUTE_CEILING)
                )

                if is_active_input:
                    # User is actively typing or clicking -> wide awake and focused!
                    closed_t = 0.0
                    away_t = 0.0
                    state = "FOCUSED"
                else:
                    if eyes_closed:
                        closed_t += dt
                    else:
                        closed_t = max(0.0, closed_t - dt * 3.0)

                    # Looking down at keyboard while working is normal, not distraction
                    is_distracted = looking_away and not looking_down_at_keyboard and not eyes_closed
                    away_t = away_t + dt if is_distracted else max(0.0, away_t - dt * 2.0)
                    yawn_t = yawn_t + dt if f["mar"] > MAR_YAWN else 0

                    if yawn_t >= YAWN_S and not yawned:
                        yawns += 1
                        yawned = True
                        trigger_alert(
                            kind="yawn",
                            cat_text="Feeling sleepy? 🥱\nTake a stretch!",
                            spoken_text="You seem sleepy!",
                            duration=4.0
                        )
                    if yawn_t == 0:
                        yawned = False

                    if closed_t >= EYES_CLOSED_S:
                        state = "SLEEPY"
                        trigger_alert(
                            kind="sleepy",
                            cat_text="Wake up! 😴\nYou got this!",
                            spoken_text="Wake up!",
                            duration=4.0
                        )
                    elif away_t >= AWAY_WARN_S:
                        state = "DISTRACTED"
                        if away_t >= AWAY_STRONG_S:
                            trigger_alert(
                                kind="away_strong",
                                cat_text="Hey! 🐾\nGet back to work!",
                                spoken_text="Hey! Get back to work!",
                                duration=5.0
                            )
                        else:
                            trigger_alert(
                                kind="away",
                                cat_text="Focus! 🐾\nEyes on screen",
                                spoken_text="Focus!",
                                duration=3.5
                            )
                    else:
                        state = "FOCUSED"

        _current_state = state

        # Stats
        if base is not None and state in stats:
            stats[state] += dt
            if state == "DISTRACTED" and not was_distracted:
                distractions += 1
            was_distracted = state == "DISTRACTED"
            cur_focus = cur_focus + dt if state == "FOCUSED" else 0
            longest_focus = max(longest_focus, cur_focus)

        # Optional debug preview (only if requested by --preview flag)
        if show_preview:
            total = max(sum(stats.values()), 1e-6)
            score = stats["FOCUSED"] / total
            colors = {"FOCUSED": (0, 200, 0), "DISTRACTED": (0, 140, 255),
                      "SLEEPY": (0, 0, 255), "NO FACE": (160, 160, 160),
                      "CALIBRATING": (255, 200, 0)}
            c = colors.get(state, (255, 255, 255))
            cv2.rectangle(frame, (0, 0), (w, 110), (30, 30, 30), -1)
            cv2.putText(frame, f"Status: {state}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, c, 2)
            cv2.imshow("Focus Monitor Preview (q = quit)", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                _running = False
                break
        else:
            # Headless mode: light throttle sleep so loop doesn't burn 100% CPU unnecessarily
            time.sleep(0.01)

    cap.release()
    if show_preview:
        cv2.destroyAllWindows()
    if tray_icon:
        try:
            tray_icon.stop()
        except Exception:
            pass
    if _popup:
        _popup.close()

    report(stats, distractions, yawns, longest_focus)


def report(stats, distractions, yawns, longest_focus):
    fmt = lambda s: f"{int(s // 3600)}h {int(s % 3600 // 60):02d}m {int(s % 60):02d}s"
    total = sum(stats.values())
    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_file = os.path.join(base_dir, "focus_report.txt")
    lines = [
        f"Focus Report - {datetime.now():%Y-%m-%d %H:%M}",
        "-" * 36,
        f"Total session:  {fmt(total)}",
        f"Focused:        {fmt(stats['FOCUSED'])}",
        f"Distracted:     {fmt(stats['DISTRACTED'])}",
        f"Drowsy:         {fmt(stats['SLEEPY'])}",
        f"Away from desk: {fmt(stats['NO FACE'])}",
        f"Distractions:   {distractions}",
        f"Yawns:          {yawns}",
        f"Longest focus:  {fmt(longest_focus)}",
        f"Focus score:    {stats['FOCUSED'] / total * 100:.0f}%" if total else "No data.",
    ]
    text = "\n".join(lines)
    print("\n" + text)
    try:
        with open(report_file, "a", encoding="utf-8") as fh:
            fh.write(text + "\n\n")
    except Exception as e:
        print("[Report Error]", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Focus Monitor with Cat Alert")
    parser.add_argument("--preview", action="store_true", help="Display camera debug feed")
    args = parser.parse_args()

    # Ensure autostart shortcut exists so it runs whenever the laptop opens / logs in
    if not autostart.is_autostart_installed():
        autostart.install_autostart()

    run_monitor(show_preview=args.preview)
