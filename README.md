# Personal Focus Monitor

An intelligent, privacy-friendly personal focus monitor for Windows. It quietly tracks your attention using your webcam and MediaPipe Face Mesh in the background (no video window), and pops up an adorable cartoon cat holding a sign board whenever you get distracted, sleepy, or look away from your screen.

---

## ✨ Features

- **🐱 Cute Cat Board Alert**: Whenever you lose focus, an adorable cat pops up in the bottom-right corner of your screen holding a wooden sign board with friendly reminders (*"Focus! 🐾"*, *"Wake up! 😴"*, *"Hey! Get back to work!"*).
- **🙈 Completely Headless**: No camera video window taking up screen space or distracting you. Everything runs quietly in the background.
- **💻 Runs on Laptop Startup**: Automatically launches silently when you open or log into your laptop (`shell:startup` shortcut).
- **🔋 Laptop Lid / Sleep Resilient**: If you close your laptop lid or put it to sleep, the monitor gracefully waits and automatically reconnects to the webcam when you return.
- **🗣️ Audio / TTS Alerts**: Optional voice alerts via Text-to-Speech (can be toggled on/off anytime).
- **📌 System Tray Controls**: Small cat icon in the Windows taskbar notification area to recalibrate, toggle sound, view reports, or exit.
- **📊 Focus Reports**: Automatically logs your daily session metrics (total time, focus percentage, distractions, yawns, longest focus streak) to `focus_report.txt`.

---

## 🚀 How to Run

### Automatic (On Laptop Startup / Log in)
You don't need to do anything! The app automatically starts in the background whenever you open and log into your laptop via the Windows Startup shortcut (`FocusMonitor.lnk`).

### Manual Launch (Whenever you want to start it)
- **Option A (Easiest - 1 click, completely silent):**
  Double-click [`run_in_background.vbs`](run_in_background.vbs). This launches it in the background with no terminal window.
- **Option B (Via PowerShell / Command Prompt):**
  ```powershell
  .\venv\Scripts\pythonw.exe focus_monitor.py
  ```
- **Option C (Debug / Camera Preview Mode):**
  If you want to see the live camera feed and landmark detection overlays:
  ```powershell
  .\venv\Scripts\python.exe focus_monitor.py --preview
  ```
  *(In preview mode: press `q` to quit, `c` to recalibrate).*

### 🛑 How to Stop / Close It
- **Via System Tray**: Right-click the small 🐱 cat icon in your Windows taskbar tray (near the clock) and click **Exit**.
- **Via PowerShell**:
  ```powershell
  taskkill /F /IM pythonw.exe
  ```

---

## ⚙️ How It Works

1. **Calibration**: For the first ~50 frames after launch, look naturally at your screen. The monitor learns your normal head pitch, yaw, eye aspect ratio (EAR), and gaze direction.
2. **Focus Detection**:
   - **Drowsy / Sleepy Eyes**: Eyes closed or drooping (EAR < 82% of baseline or EAR < 0.21) for **> 0.85 seconds** (fast detection while eyes are still shut).
   - **Head Nodding Off**: Downward head tilt combined with drooping eyes triggers faster microsleep alert (**~0.65 seconds**).
   - **Distracted / Looking Away**: Head yaw, pitch, or gaze deviating from baseline for > 2.5 seconds.
   - **Prolonged Distraction**: Looking away for > 8.0 seconds triggers a stronger prompt.
   - **Yawning**: Mouth aspect ratio (MAR) wide open for > 1.3 seconds.
   - **Away from Desk**: Face not detected for > 3.5 seconds.
3. **Cat Popup**:
   - The transparent cat window appears smoothly above your taskbar.
   - Click anywhere on the cat to dismiss it immediately, or it will auto-dismiss once you refocus.

---

## 📌 System Tray Menu

Right-click the 🐱 cat icon in your Windows taskbar tray:
- **Status Indicator**: Displays current state (*FOCUSED*, *DISTRACTED*, *SLEEPY*, *CALIBRATING*).
- **Recalibrate Normal Pose**: Resets your baseline pose whenever you change seating posture.
- **Test Cat Popup**: Displays the cat popup for a quick preview.
- **Sound / TTS Alerts**: Toggle spoken audio alerts on or off.
- **Start with Windows**: Toggle automatic startup with Windows.
- **View Focus Report**: Opens [`focus_report.txt`](focus_report.txt) in Notepad.
- **Exit**: Saves session stats and cleanly terminates the monitor.

---

## 📁 Project Structure

| File | Description |
|---|---|
| `focus_monitor.py` | Main application logic: webcam capture, MediaPipe detection, alerts, and system tray. |
| `cat_popup.py` | Transparent Tkinter overlay that dynamically renders the cat and message board. |
| `autostart.py` | Helper script to register or remove the Windows Startup shortcut. |
| `run_in_background.vbs` | Silent VBS launcher script for one-click background execution. |
| `cat_board_cropped.png` | High-resolution transparent cartoon cat graphic holding the board. |
| `cat_icon.ico` | Taskbar system tray icon. |
| `focus_report.txt` | Persistent log file with time breakdowns and focus scores. |

---

## 🛠️ Requirements & Installation

If setting up on a new machine:
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install opencv-python mediapipe numpy pillow pystray pyttsx3 pywin32
```

---

## 📄 Example Focus Report

```text
Focus Report - 2026-10-02 14:05
------------------------------------
Total session:  1h 15m 20s
Focused:        1h 02m 45s
Distracted:     0h 08m 12s
Drowsy:         0h 02m 10s
Away from desk: 0h 02m 13s
Distractions:   4
Yawns:          2
Longest focus:  0h 34m 10s
Focus score:    83%
```
