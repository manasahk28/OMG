"""
Helper module to manage Windows startup for Focus Monitor.
"""
import os
import sys

def get_startup_shortcut_path():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    startup_dir = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(startup_dir, "FocusMonitor.lnk")

def is_autostart_installed():
    path = get_startup_shortcut_path()
    return path is not None and os.path.exists(path)

def install_autostart():
    path = get_startup_shortcut_path()
    if not path:
        return False, "Could not locate APPDATA startup directory."
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pythonw = os.path.join(base_dir, "venv", "Scripts", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    
    script_path = os.path.join(base_dir, "focus_monitor.py")
    icon_path = os.path.join(base_dir, "cat_icon.ico")
    
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)
        shortcut.TargetPath = pythonw
        shortcut.Arguments = f'"{script_path}"'
        shortcut.WorkingDirectory = base_dir
        shortcut.Description = "Personal Focus Monitor with Cute Cat Board Alert"
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        shortcut.Save()
        return True, path
    except Exception as e:
        return False, str(e)

def remove_autostart():
    path = get_startup_shortcut_path()
    if path and os.path.exists(path):
        try:
            os.remove(path)
            return True, "Removed startup shortcut."
        except Exception as e:
            return False, str(e)
    return True, "Startup shortcut not present."

if __name__ == "__main__":
    success, msg = install_autostart()
    print("Install status:", success, msg)
