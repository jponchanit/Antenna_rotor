import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess
import threading
import time
import json
import os
import math

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

# =====================
# OS DETECTION
# =====================
IS_WINDOWS = os.name == "nt"

ROTCTLD_BIN = "rotctld.exe" if IS_WINDOWS else "rotctld"
ROTCTL_BIN  = "rotctl.exe"  if IS_WINDOWS else "rotctl"

DEFAULT_HAMLIB_PATHS = [
    "/usr/bin",
    "/usr/local/bin",
    "/bin",
    "C:\\Program Files\\hamlib-w64-4.6.3\\bin",
    "C:\\Program Files\\hamlib\\bin",
    "C:\\Program Files (x86)\\hamlib\\bin"
]

CONFIG_FILE = "rotor_config.json"

# =====================
# COMPASS WIDGET
# =====================
class Compass(tk.Canvas):
    def __init__(self, parent, size=200):
        super().__init__(parent, width=size, height=size, bg="white")
        self.size = size
        self.center = size / 2
        self.radius = size * 0.45
        self.pointer = None
        self.draw_face()
        self.update_azimuth(0)

    def draw_face(self):
        self.create_oval(
            self.center - self.radius,
            self.center - self.radius,
            self.center + self.radius,
            self.center + self.radius,
            outline="gray",
            width=2
        )

        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x1 = self.center + self.radius * math.sin(rad)
            y1 = self.center - self.radius * math.cos(rad)
            x2 = self.center + (self.radius - 10) * math.sin(rad)
            y2 = self.center - (self.radius - 10) * math.cos(rad)
            self.create_line(x1, y1, x2, y2, width=2)

            if angle % 90 == 0:
                label = {0: "N", 90: "E", 180: "S", 270: "W"}[angle]
                self.create_text(
                    self.center + (self.radius + 18) * math.sin(rad),
                    self.center - (self.radius + 18) * math.cos(rad),
                    text=label,
                    font=("Arial", 14, "bold")
                )

    def update_azimuth(self, az):
        if self.pointer:
            self.delete(self.pointer)
        rad = math.radians(az)
        x = self.center + self.radius * 0.9 * math.sin(rad)
        y = self.center - self.radius * 0.9 * math.cos(rad)
        self.pointer = self.create_line(
            self.center, self.center, x, y,
            arrow=tk.LAST, fill="red", width=3
        )

# =====================
# ELEVATION WIDGET
# =====================
class ElevationIndicator(tk.Canvas):
    def __init__(self, parent, size=200):
        super().__init__(parent, width=size, height=size//2 + 20, bg="white")
        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.radius = size * 0.45
        self.pointer = None
        self.draw_arc()
        self.update_elevation(0)

    def draw_arc(self):
        self.create_arc(
            self.cx - self.radius, self.cy - self.radius,
            self.cx + self.radius, self.cy + self.radius,
            start=0, extent=180, style=tk.ARC, width=2
        )

    def update_elevation(self, el):
        el = max(0, min(180, el))
        if self.pointer:
            self.delete(self.pointer)
        rad = math.radians(180 - el)
        x = self.cx + self.radius * math.cos(rad)
        y = self.cy - self.radius * math.sin(rad)
        self.pointer = self.create_line(
            self.cx, self.cy, x, y,
            arrow=tk.LAST, fill="blue", width=3
        )

# =====================
# MAIN GUI
# =====================
class RotorControlGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rotor Control")
        self.geometry("1250x900")

        self.rotctld_process = None
        self.config = self.load_config()

        self.create_widgets()
        self.find_hamlib()
        self.update_ports()
        self.after(2000, self.monitor)

    # -----------------
    # CONFIG
    # -----------------
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {
            "hamlib_path": "/usr/bin",
            "model": "901",
            "port": "/dev/ttyUSB0",
            "baud": "600",
            "host": "127.0.0.1",
            "tcp": "4533"
        }

    def save_config(self):
        self.config.update({
            "hamlib_path": self.hamlib_path.get(),
            "model": self.model.get(),
            "port": self.serial.get(),
            "baud": self.baud.get(),
            "host": self.host.get(),
            "tcp": self.tcp.get()
        })
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    # -----------------
    # UI
    # -----------------
    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(frame)
        left.pack(side="left", fill="y")

        right = ttk.Frame(frame)
        right.pack(side="right", fill="both", expand=True)

        self.hamlib_path = tk.StringVar(value=self.config["hamlib_path"])
        self.model = tk.StringVar(value=self.config["model"])
        self.serial = tk.StringVar(value=self.config["port"])
        self.baud = tk.StringVar(value=self.config["baud"])
        self.host = tk.StringVar(value=self.config["host"])
        self.tcp = tk.StringVar(value=self.config["tcp"])

        ttk.Label(left, text="Hamlib Path").pack(anchor="w")
        ttk.Entry(left, textvariable=self.hamlib_path, width=40).pack()

        ttk.Label(left, text="Serial Port").pack(anchor="w")
        self.port_combo = ttk.Combobox(left, textvariable=self.serial)
        self.port_combo.pack()

        ttk.Button(left, text="Start rotctld", command=self.start_rotctld).pack(pady=5)
        ttk.Button(left, text="Stop rotctld", command=self.stop_rotctld).pack(pady=5)

        self.logbox = scrolledtext.ScrolledText(left, width=50, height=20)
        self.logbox.pack(pady=10)

        self.compass = Compass(right, 300)
        self.compass.pack(pady=20)

        self.elevation = ElevationIndicator(right, 250)
        self.elevation.pack()

    # -----------------
    # LOGGING
    # -----------------
    def log(self, msg):
        self.logbox.insert(tk.END, msg + "\n")
        self.logbox.see(tk.END)

    # -----------------
    # HAMLIB
    # -----------------
    def find_hamlib(self):
        for p in DEFAULT_HAMLIB_PATHS:
            if os.path.exists(os.path.join(p, ROTCTLD_BIN)):
                self.hamlib_path.set(p)
                return

    def start_rotctld(self):
        self.save_config()
        exe = os.path.join(self.hamlib_path.get(), ROTCTLD_BIN)

        cmd = [
            exe,
            "-m", self.model.get(),
            "-r", self.serial.get(),
            "-s", self.baud.get(),
            "-T", self.host.get(),
            "-t", self.tcp.get()
        ]

        kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.rotctld_process = subprocess.Popen(cmd, **kwargs)
        self.log("rotctld started")

    def stop_rotctld(self):
        if self.rotctld_process:
            self.rotctld_process.terminate()
            self.rotctld_process = None
            self.log("rotctld stopped")

    # -----------------
    # SERIAL
    # -----------------
    def update_ports(self):
        if list_ports:
            ports = [p.device for p in list_ports.comports()]
            self.port_combo["values"] = ports

    def monitor(self):
        self.after(5000, self.monitor)

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    app = RotorControlGUI()
    app.mainloop()
