from .compositor import Compositor, detect_compositor

import os
from time import time
import errno
import subprocess
import select
from datetime import datetime
from collections.abc import Generator
import json

from Xlib import display as xdisplay

class Windows:
    def __init__(self):
        self.compositor: Compositor = detect_compositor()

        self.wm_handler:WMHandler = WMHandler(self.compositor)

    def get_windows(self):
        return self.wm_handler.get_windows()

class WMHandler:
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

        path = os.path.expanduser("~/.local/share/pc-stats/scripts/windows.js")
        with open(path, "w") as f:
            _ = f.write("""\
let windows = workspace.stackingOrder;

let active = 0;
for (let w of windows) {
    if (w.hidden) {
        continue;
    }
    if (!w.normalWindow) {
        continue;
    }
    if (w.active) {
        active = w.pid;
    }
    const data = `{\
        "name": "${w.resourceName}",\
        "caption": "${w.caption}",\
        "pid": ${w.pid},\
        "desktop": "${w.desktops[0].x11DesktopNumber - 1}",\
        "geometry": [${w.x}, ${w.y}, ${w.width}, ${w.height}],\
        "minimized": ${w.minimized}\
    }`;
    print("windows:", data);
}
print("windows:", `{"active_pid": ${active}, "current_desktop": ${workspace.currentDesktop.x11DesktopNumber - 1}}`)
""")

    def _get_windows_kde_wayland(self):
        script = os.path.expanduser("~/.local/share/pc-stats/scripts/windows.js")
        now = datetime.fromtimestamp(time() - 1).strftime("%H:%M:%S")

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
            capture_output=True, text=True
        )

        lines = [line for line in journal.stdout.splitlines() if "windows: " in line]
        return lines

    def get_windows(self):
        data = []
        match self.compositor:
            case Compositor.KDE_WAYLAND:
                data =  self._get_windows_kde_wayland()
            case _:
                return None

        if not data:
            print("Couldn't retrieve window data")
            return None

        data = list(map(
            lambda line: json.loads(line.removeprefix("js: windows: "))
        , data))
        # list of window dicts + snapshot dict

        windows:list[dict] = data[:-1]
        snapshot = data[-1]

        return {
            "windows": windows,
            "snapshot": snapshot,
        }

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

    def get_position(self):# -> tuple[int, int] | None:
        match self.compositor:
            case Compositor.KDE_WAYLAND:
                return self._get_pos_kde_wayland()
            case Compositor.X11 | Compositor.GNOME_WAYLAND:
                return self._get_pos_xlib()
            case Compositor.HYPRLAND:
                return self._get_pos_hyprland()
            case _:
                return None
