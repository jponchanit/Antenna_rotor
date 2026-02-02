import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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


# ------------------ Compass Widget ------------------

class Compass(tk.Canvas):
    def __init__(self, parent, size=200):
        super().__init__(parent, width=size, height=size, bg="white")
        self.size = size
        self.center = size / 2
        self.radius = size * 0.45
        self.pointer = None
        self.draw_static()
        self.update_azimuth(0)

    def draw_static(self):
        self.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            outline="gray", width=2
        )
        for a in range(0, 360, 30):
            r = math.radians(a)
            x = self.center + self.radius * math.sin(r)
            y = self.center - self.radius * math.cos(r)
            self.create_line(self.center, self.center, x, y, fill="lightgray")

    def update_azimuth(self, angle):
        if self.pointer:
            self.delete(self.pointer)
        r = math.radians(angle)
        x = self.center + self.radius * math.sin(r)
        y = self.center - self.radius * math.cos(r)
        self.pointer = self.create_line(
            self.center, self.center, x, y,
            arrow=tk.LAST, fill="red", width=3
        )


# ------------------ Elevation Widget ------------------

class ElevationIndicator(tk.Canvas):
    def __init__(self, parent, size=200):
        super().__init__(parent, width=size, height=size//2 + 20, bg="white")
        self.size = size
        self.center_x = size / 2
        self.center_y = size / 2
        self.radius = size * 0.45
        self.pointer = None
        self.draw_static()
        self.update_elevation(0)

    def draw_static(self):
        self.create_arc(
            self.center_x - self.radius, self.center_y - self.radius,
            self.center_x + self.radius, self.center_y + self.radius,
            start=0, extent=180, style=tk.ARC, width=2
        )

    def update_elevation(self, angle):
        if self.pointer:
            self.delete(self.pointer)
        angle = max(0, min(180, angle))
        r = math.radians(180 - angle)
        x = self.center_x + self.radius * math.cos(r)
        y = self.center_y - self.radius * math.sin(r)
        self.pointer = self.create_line(
            self.center_x, self.center_y, x, y,
            arrow=tk.LAST, fill="blue", width=3
        )


# ------------------ Main GUI ------------------

class RotorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rotor Control (Linux / Raspberry Pi)")
        self.geometry("1100x800")

        self.rotctld = None
        self.config_file = "rotor_comfig.json"

        self.config_data = self.load_config()

        self.create_widgets()
        self.update_ports()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                return json.load(f)
        return {
            "model": "601",
            "port": "/dev/ttyUSB0",
            "baud": "1200",
            "host": "127.0.0.1",
            "tcp": "4533"
        }

    def save_config(self):
        data = {
            "model": self.model.get(),
            "port": self.port.get(),
            "baud": self.baud.get(),
            "host": self.host.get(),
            "tcp": self.tcp.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Settings
        settings = ttk.LabelFrame(frame, text="rotctld Settings")
        settings.pack(fill="x", pady=5)

        self.model = tk.StringVar(value=self.config_data["model"])
        self.port = tk.StringVar(value=self.config_data["port"])
        self.baud = tk.StringVar(value=self.config_data["baud"])
        self.host = tk.StringVar(value=self.config_data["host"])
        self.tcp = tk.StringVar(value=self.config_data["tcp"])

        ttk.Label(settings, text="Model").grid(row=0, column=0)
        ttk.Entry(settings, textvariable=self.model, width=10).grid(row=0, column=1)

        ttk.Label(settings, text="Port").grid(row=1, column=0)
        self.port_box = ttk.Combobox(settings, textvariable=self.port, width=15)
        self.port_box.grid(row=1, column=1)
        ttk.Button(settings, text="Refresh", command=self.update_ports).grid(row=1, column=2)

        ttk.Label(settings, text="Baud").grid(row=2, column=0)
        ttk.Entry(settings, textvariable=self.baud, width=10).grid(row=2, column=1)

        ttk.Button(settings, text="Start", command=self.start_rotctld).grid(row=3, column=0)
        ttk.Button(settings, text="Stop", command=self.stop_rotctld).grid(row=3, column=1)

        # Control
        control = ttk.LabelFrame(frame, text="Control")
        control.pack(fill="x", pady=5)

        self.az = tk.StringVar(value="0")
        self.el = tk.StringVar(value="0")

        ttk.Label(control, text="Az").grid(row=0, column=0)
        ttk.Entry(control, textvariable=self.az).grid(row=0, column=1)

        ttk.Label(control, text="El").grid(row=1, column=0)
        ttk.Entry(control, textvariable=self.el).grid(row=1, column=1)

        ttk.Button(control, text="Set", command=self.set_position).grid(row=2, column=0)
        ttk.Button(control, text="Get", command=self.get_position).grid(row=2, column=1)

        # Display
        display = ttk.LabelFrame(frame, text="Display")
        display.pack(fill="both", expand=True)

        self.compass = Compass(display, 300)
        self.compass.pack(pady=10)

        self.elev = ElevationIndicator(display, 250)
        self.elev.pack(pady=10)

        # Log
        self.log = scrolledtext.ScrolledText(frame, height=8)
        self.log.pack(fill="both", expand=True)

    def update_ports(self):
        if list_ports:
            ports = [p.device for p in list_ports.comports()]
            self.port_box["values"] = ports
            if ports and self.port.get() not in ports:
                self.port.set(ports[0])

    def start_rotctld(self):
        self.save_config()
        cmd = [
            "rotctld",
            "-m", self.model.get(),
            "-r", self.port.get(),
            "-s", self.baud.get(),
            "-T", self.host.get(),
            "-t", self.tcp.get(),
            "-vvvv"
        ]
        try:
            self.rotctld = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            threading.Thread(target=self.read_output, daemon=True).start()
            self.log_msg("rotctld started")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_rotctld(self):
        if self.rotctld:
            self.rotctld.terminate()
            self.rotctld = None
            self.log_msg("rotctld stopped")

    def read_output(self):
        for line in self.rotctld.stdout:
            self.log_msg(line.strip())

    def rotctl(self, args):
        cmd = ["rotctl", "-m", "2", "-r", f"{self.host.get()}:{self.tcp.get()}"] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()

    def set_position(self):
        self.rotctl(["P", self.az.get(), self.el.get()])

    def get_position(self):
        out = self.rotctl(["p"]).splitlines()
        if len(out) >= 2:
            az = float(out[0])
            el = float(out[1])
            self.compass.update_azimuth(az)
            self.elev.update_elevation(el)

    def log_msg(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)


if __name__ == "__main__":
    app = RotorGUI()

    app.mainloop()
