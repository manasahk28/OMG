"""
Cat Overlay Popup for Personal Focus Monitor
Displays ONLY the cute cartoon cat holding a sign board with customizable alert messages.
100% transparent desktop cutout overlay.
Automatically adjusts for Windows Display Scaling (DPI) so it is ALWAYS on-screen.
"""
import os
import time
import queue
import threading
import ctypes
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "cat_board_cropped.png")

# Standard pure magenta transparent key for Windows
TRANS_KEY = "#ff00ff"
TRANS_RGB = (255, 0, 255)

class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class CatPopup:
    def __init__(self, width=180, height=195):
        self.width = width
        self.height = height
        self.msg_queue = queue.Queue()
        self.is_visible = False
        self.hide_timer = None
        self.ready_event = threading.Event()
        
        # Load and resize base cat graphic to compact size
        raw_img = Image.open(IMAGE_PATH).convert("RGBA")
        self.base_cat = raw_img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        
        # Start UI loop in dedicated thread
        self.thread = threading.Thread(target=self._run_ui, daemon=True)
        self.thread.start()
        self.ready_event.wait(timeout=3.0)

    def _get_target_coords(self):
        """Calculates bottom-right screen coordinates above the taskbar in current DPI scaling."""
        try:
            rect = _RECT()
            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                x = rect.right - self.width - 15
                y = rect.bottom - self.height - 10
                return max(10, x), max(10, y)
        except Exception:
            pass
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return max(10, sw - self.width - 15), max(10, sh - self.height - 45)

    def _get_font(self, size):
        for font_name in ["comicbd.ttf", "segoeuib.ttf", "arialbd.ttf"]:
            p = os.path.join(r"C:\Windows\Fonts", font_name)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def _render_image(self, message):
        img = self.base_cat.copy()
        draw = ImageDraw.Draw(img)
        
        lines = message.strip().split("\n")
        max_len = max(len(l) for l in lines) if lines else 0
        if len(lines) >= 3 or max_len > 16:
            font_size = 13
        elif len(lines) == 2 or max_len > 10:
            font_size = 15
        else:
            font_size = 18
            
        font = self._get_font(font_size)
        
        cw, ch = img.size
        cx = cw // 2
        cy = int(ch * 0.72)
        
        fill_color = (68, 38, 16, 255)
        draw.multiline_text(
            (cx, cy),
            message,
            font=font,
            fill=fill_color,
            anchor="mm",
            align="center",
            spacing=3
        )
        
        # Composite onto magenta: transparent areas become magenta for Windows colorkey
        bg = Image.new("RGB", (cw, ch), TRANS_RGB)
        bg.paste(img, (0, 0), img)
        return bg

    def _run_ui(self):
        self.root = tk.Tk()
        self.root.title("Cat Focus Alert")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=TRANS_KEY)
        self.root.attributes("-transparentcolor", TRANS_KEY)
        
        x, y = self._get_target_coords()
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.withdraw() # Start hidden
        
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANS_KEY,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", lambda e: self.hide())
        
        self._current_photo = None
        self._img_cache = {}
        
        self.ready_event.set()
        
        self.root.after(20, self._process_events)
        self.root.mainloop()

    def _process_events(self):
        try:
            while not self.msg_queue.empty():
                cmd, arg = self.msg_queue.get_nowait()
                if cmd == "SHOW":
                    msg, duration = arg
                    self._do_show(msg, duration)
                elif cmd == "HIDE":
                    self._do_hide()
        except Exception:
            pass
        self.root.after(20, self._process_events)

    def _do_show(self, message, duration=4.5):
        try:
            if message in self._img_cache:
                self._current_photo = self._img_cache[message]
            else:
                pil_img = self._render_image(message)
                self._current_photo = ImageTk.PhotoImage(pil_img)
                self._img_cache[message] = self._current_photo
            
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._current_photo)
            self.canvas.image = self._current_photo
            
            x, y = self._get_target_coords()
            self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.is_visible = True
            
            if self.hide_timer is not None:
                self.root.after_cancel(self.hide_timer)
                self.hide_timer = None
                
            if duration and duration > 0:
                self.hide_timer = self.root.after(int(duration * 1000), self._do_hide)
        except Exception as e:
            print("[CatPopup Error]", e)

    def _do_hide(self):
        try:
            if self.is_visible:
                self.root.withdraw()
                self.is_visible = False
            if self.hide_timer is not None:
                self.root.after_cancel(self.hide_timer)
                self.hide_timer = None
        except Exception:
            pass

    def show(self, message, duration=4.5):
        self.msg_queue.put(("SHOW", (message, duration)))

    def hide(self):
        self.msg_queue.put(("HIDE", None))

    def close(self):
        try:
            if hasattr(self, "root"):
                self.root.quit()
        except Exception:
            pass


if __name__ == "__main__":
    popup = CatPopup()
    popup.show("Focus!\nKeep going! 🐾", duration=4.0)
    time.sleep(4.5)
