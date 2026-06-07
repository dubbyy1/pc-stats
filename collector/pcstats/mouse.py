import re

from .compositor import Compositor, detect_compositor

import os
from time import time
import errno
import subprocess
import select
from datetime import datetime
from collections.abc import Generator

from evdev import InputDevice, InputEvent, ecodes, list_devices
from Xlib import display as xdisplay

class Mouse:
    def __init__(self):
        self.compositor: Compositor = detect_compositor()
        self.devices: list[InputDevice] = []
        self.detect_mouse()

        self.position_handler:PositionHandler = PositionHandler(self.compositor)

    def detect_mouse(self):
        valid_mice = []
        for path in list_devices():
            dev = InputDevice(path)
            capabilities = dev.capabilities()
            if ecodes.EV_KEY not in capabilities:
                continue

            if ecodes.BTN_LEFT not in capabilities[ecodes.EV_KEY]:
                continue
            if ecodes.BTN_RIGHT not in capabilities[ecodes.EV_KEY]:
                continue
            if ecodes.BTN_MIDDLE not in capabilities[ecodes.EV_KEY]:
                continue

            if ecodes.EV_REL not in capabilities:
                continue

            if ecodes.REL_X not in capabilities[ecodes.EV_REL]:
                continue
            if ecodes.REL_Y not in capabilities[ecodes.EV_REL]:
                continue
            valid_mice.append(dev)

        if valid_mice:
            if valid_mice != self.devices:
                for device in valid_mice:
                    if device not in self.devices:
                        print(f"Mouse Connected - {device.name}")
                self.devices = valid_mice
        else:
            self.devices = []

    def get_position(self) -> tuple[int, int] | None:
        return self.position_handler.get_position()

    def _read_all(self):
        while True:
            readable_devices, _, _ = select.select(self.devices, [], [], 5)
            if not readable_devices:
                self.detect_mouse()
                continue
            for device in readable_devices:
                try:
                    for event in device.read():
                        yield event
                except OSError as e:
                    # handle disconnect
                    if e.errno == errno.ENODEV:
                        self.devices.remove(device)
                        print(f"Mouse disconnected - {device.name}")
                    else:
                        raise e

    def poll(self) -> Generator[tuple[float, int, int, str]]:
        for event in self._read_all():
            if event.type == ecodes.EV_KEY and event.value == 1:
                pos = self.get_position()
                if pos:
                    MOUSE_BUTTONS = {ecodes.BTN_LEFT: "LEFT", ecodes.BTN_RIGHT: "RIGHT", ecodes.BTN_MIDDLE: "MIDDLE"}
                    yield (time(), pos[0], pos[1], MOUSE_BUTTONS[event.code])

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
        try:
            x, y = lines[-1].split(",")
            return (int(x), int(y))
        except ValueError as e:
            print(e)
            return None

    def _get_pos_xlib(self):
        display = xdisplay.Display()
        root = display.screen().root
        pos = root.query_pointer()
        display.close()

        return (pos['root_x'], pos['root_y'])

    # UNTESTED
    def _get_pos_hyprland(self) -> tuple[int, int] | None:
        import socket as sock
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not sig:
            return None

        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        socket_path = f"{runtime_dir}/hypr/{sig}/.socket.sock"

        try:
            with sock.socket(sock.AF_UNIX, sock.SOCK_STREAM) as s:
                s.connect(socket_path)
                s.sendall(b"cursorpos")
                data = s.recv(64).decode().strip()
            x, y = data.split(",")
            return (int(x), int(y))
        except Exception:
            return None


    def get_position(self) -> tuple[int, int] | None:
        match self.compositor:
            case Compositor.KDE_WAYLAND:
                return self._get_pos_kde_wayland()
            case Compositor.X11 | Compositor.GNOME_WAYLAND:
                return self._get_pos_xlib()
            case Compositor.HYPRLAND:
                return self._get_pos_hyprland()
            case _:
                return None
