from .compositor import Compositor, detect_compositor

import os
import subprocess
from datetime import datetime

from evdev import InputDevice, ecodes, list_devices

class Mouse:
    def __init__(self):
        self.compositor: Compositor = detect_compositor()
        self.device: InputDevice = self.detect_mouse()

        self.position_handler:PositionHandler = PositionHandler(self.compositor)

    def detect_mouse(self):
        all_devices = [InputDevice(path) for path in list_devices()]
        for d in all_devices:
            if d.name == "Logitech USB Receiver Mouse":
                return d

    def get_position(self) -> tuple[int, int] | None:
        return self.position_handler.get_position()

    def poll(self) -> tuple[int,int,str] | None:
        for event in self.device.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:
                pos = self.get_position()
                if pos:
                    MOUSE_BUTTONS = {ecodes.BTN_LEFT: "LEFT", ecodes.BTN_RIGHT: "RIGHT", ecodes.BTN_MIDDLE: "MIDDLE"}
                    return (pos[0], pos[1], MOUSE_BUTTONS[event.code])

class PositionHandler:
    def __init__(self, compositor: Compositor):
        self.compositor:Compositor = compositor

        match self.compositor:
            case Compositor.KDE_WAYLAND:
                self.setup_kde_wayland()
            case _:
                pass

    def setup_kde_wayland(self):
        script_dir = os.path.expanduser("~/.local/share/pc-stats/scripts")
        os.makedirs(script_dir, exist_ok=True)

        path = os.path.expanduser("~/.local/share/pc-stats/scripts/mouse_pos.js")
        with open(path, "w") as f:
            _ = f.write((
                "const pos = workspace.cursorPos;\n"
                "print(pos.x.toString() + ',' + pos.y.toString());\n"
            ))

    def _get_pos_kde_wayland(self):
        script = os.path.expanduser("~/.local/share/pc-stats/scripts/mouse_pos.js")
        now = datetime.now().strftime("%H:%M:%S")

        result = subprocess.run(
            ["dbus-send", "--print-reply", "--dest=org.kde.KWin",
             "/Scripting", "org.kde.kwin.Scripting.loadScript",
             f"string:{script}"],
            capture_output=True, text=True,
        )
        num = result.stdout.strip().split()[-1]

        _ = subprocess.run(
            ["dbus-send", "--print-reply", "--dest=org.kde.KWin",
             f"/Scripting/Script{num}", "org.kde.kwin.Script.run"],
            capture_output=True,
        )
        _ = subprocess.run(
            ["dbus-send", "--print-reply", "--dest=org.kde.KWin",
             f"/Scripting/Script{num}", "org.kde.kwin.Script.stop"],
            capture_output=True,
        )

        journal = subprocess.run(
            ["journalctl", "_COMM=kwin_wayland", "-o", "cat", "--since", now],
            capture_output=True, text=True,
        )
        lines = [line.removeprefix("js: ") for line in journal.stdout.splitlines() if "," in line]
        if not lines:
            print("Mouse Position Not Found")
            return None
        x, y = lines[-1].split(",")
        return (int(x), int(y))

    def get_position(self) -> tuple[int, int] | None:
        match self.compositor:
            case Compositor.KDE_WAYLAND:
                return self._get_pos_kde_wayland()
            case _:
                return None
