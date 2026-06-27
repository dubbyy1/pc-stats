from .compositor import Compositor, detect_compositor

import json
import os
import shutil
import subprocess
from datetime import datetime
from time import time
from typing import Any

from Xlib import X
from Xlib.display import Display


WindowRecord = dict[str, Any]
WindowSnapshot = dict[str, Any]


class Windows:
    def __init__(self):
        self.compositor: Compositor = detect_compositor()
        self.wm_handler: WMHandler = WMHandler(self.compositor)

    def get_windows(self) -> WindowSnapshot | None:
        return self.wm_handler.get_windows()


class WMHandler:
    def __init__(self, compositor: Compositor):
        self.compositor: Compositor = compositor

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
const windows = workspace.stackingOrder;
const activeWindow = workspace.activeWindow;

for (let w of windows) {
    if (w.hidden || !w.normalWindow) {
        continue;
    }

    const desktop = w.onAllDesktops || !w.desktops || w.desktops.length === 0
        ? -1
        : w.desktops[0].x11DesktopNumber - 1;

    const data = {
        name: w.resourceName || "",
        caption: w.caption || "",
        pid: w.pid || 0,
        desktop,
        geometry: w.minimized ? [-1, -1, -1, -1] : [w.x, w.y, w.width, w.height],
        minimized: !!w.minimized
    };
    print("windows: " + JSON.stringify(data));
}

const snapshot = {
    active: activeWindow ? (activeWindow.resourceName || "") : "",
    current_desktop: workspace.currentDesktop
        ? workspace.currentDesktop.x11DesktopNumber - 1
        : 0
};
print("windows: " + JSON.stringify(snapshot));
""")

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if shutil.which(args[0]) is None:
            return None

        try:
            return subprocess.run(args, capture_output=True, text=True, check=False)
        except OSError:
            return None

    def _normal_window(
        self,
        name: str,
        caption: str,
        pid: int,
        desktop: int,
        geometry: list[int],
        minimized: bool = False,
    ) -> WindowRecord:
        return {
            "name": name or caption or "unknown",
            "caption": caption or "",
            "pid": pid or 0,
            "desktop": desktop,
            "geometry": geometry,
            "minimized": minimized,
        }

    def _snapshot(self, windows: list[WindowRecord], active: str, current_desktop: int) -> WindowSnapshot:
        return {
            "windows": windows,
            "snapshot": {
                "active": active or "",
                "current_desktop": current_desktop,
            },
        }

    def _get_windows_kde_wayland(self) -> WindowSnapshot | None:
        script = os.path.expanduser("~/.local/share/pc-stats/scripts/windows.js")
        now = datetime.fromtimestamp(time() - 1).strftime("%H:%M:%S")

        result = self._run([
            "dbus-send",
            "--print-reply",
            "--dest=org.kde.KWin",
            "/Scripting",
            "org.kde.kwin.Scripting.loadScript",
            f"string:{script}",
        ])
        if result is None or result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            num = result.stdout.strip().split()[-1]
        except IndexError:
            return None

        _ = self._run([
            "dbus-send",
            "--print-reply",
            "--dest=org.kde.KWin",
            f"/Scripting/Script{num}",
            "org.kde.kwin.Script.run",
        ])
        _ = self._run([
            "dbus-send",
            "--print-reply",
            "--dest=org.kde.KWin",
            f"/Scripting/Script{num}",
            "org.kde.kwin.Script.stop",
        ])

        journal = self._run([
            "journalctl",
            "_COMM=kwin_wayland",
            "-o",
            "cat",
            "--since",
            now,
        ])
        if journal is None:
            return None

        data = []
        for line in journal.stdout.splitlines():
            marker = "windows: "
            if marker not in line:
                continue
            try:
                data.append(json.loads(line.split(marker, 1)[1]))
            except json.JSONDecodeError as e:
                print(f"Invalid KWin window data: {e}")

        if not data:
            return None

        windows = data[:-1]
        snapshot = data[-1]
        return self._snapshot(
            windows,
            str(snapshot.get("active", "")),
            int(snapshot.get("current_desktop", 0)),
        )

    def _get_atom(self, display: Display, name: str) -> int:
        return display.intern_atom(name)

    def _get_window_property(self, window: Any, atom: int) -> Any:
        try:
            prop = window.get_full_property(atom, X.AnyPropertyType)
        except Exception:
            return None
        if prop is None:
            return None
        return prop.value

    def _get_window_text(self, window: Any, atom: int) -> str:
        value = self._get_window_property(window, atom)
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if hasattr(value, "tobytes"):
            return value.tobytes().decode("utf-8", errors="replace").rstrip("\x00")
        return str(value)

    def _get_window_int(self, window: Any, atom: int, default: int = 0) -> int:
        value = self._get_window_property(window, atom)
        try:
            return int(value[0])
        except (TypeError, IndexError, ValueError):
            return default

    def _get_x11_geometry(self, window: Any, root: Any) -> list[int]:
        try:
            geometry = window.get_geometry()
            coords = window.translate_coords(root, 0, 0)
            return [coords.x, coords.y, geometry.width, geometry.height]
        except Exception:
            return [-1, -1, -1, -1]

    def _get_windows_x11(self) -> WindowSnapshot | None:
        try:
            display = Display()
        except Exception as e:
            print(f"Could not connect to X11 display: {e}")
            return None

        try:
            root = display.screen().root
            client_list_atom = self._get_atom(display, "_NET_CLIENT_LIST")
            active_window_atom = self._get_atom(display, "_NET_ACTIVE_WINDOW")
            current_desktop_atom = self._get_atom(display, "_NET_CURRENT_DESKTOP")
            wm_desktop_atom = self._get_atom(display, "_NET_WM_DESKTOP")
            wm_pid_atom = self._get_atom(display, "_NET_WM_PID")
            wm_name_atom = self._get_atom(display, "_NET_WM_NAME")

            client_ids = self._get_window_property(root, client_list_atom)
            if client_ids is None:
                return None

            active_ids = self._get_window_property(root, active_window_atom)
            active_id = int(active_ids[0]) if active_ids is not None and len(active_ids) else 0
            current_desktop = self._get_window_int(root, current_desktop_atom)

            windows = []
            active = ""
            for window_id in client_ids:
                window = display.create_resource_object("window", int(window_id))
                title = self._get_window_text(window, wm_name_atom)
                if not title:
                    title = window.get_wm_name() or ""

                pid = self._get_window_int(window, wm_pid_atom)
                desktop = self._get_window_int(window, wm_desktop_atom, -1)
                geometry = self._get_x11_geometry(window, root)

                record = self._normal_window(title, title, pid, desktop, geometry)
                windows.append(record)

                if int(window_id) == active_id:
                    active = record["name"]

            return self._snapshot(windows, active, current_desktop)
        finally:
            display.close()

    def _get_windows_hyprland(self) -> WindowSnapshot | None:
        clients_result = self._run(["hyprctl", "clients", "-j"])
        if clients_result is None or clients_result.returncode != 0:
            return None

        try:
            clients = json.loads(clients_result.stdout)
        except json.JSONDecodeError as e:
            print(f"Invalid Hyprland client data: {e}")
            return None

        active = ""
        active_result = self._run(["hyprctl", "activewindow", "-j"])
        if active_result is not None and active_result.returncode == 0:
            try:
                active_window = json.loads(active_result.stdout)
                active = active_window.get("title") or active_window.get("class") or ""
            except json.JSONDecodeError:
                pass

        current_desktop = 0
        workspace_result = self._run(["hyprctl", "activeworkspace", "-j"])
        if workspace_result is not None and workspace_result.returncode == 0:
            try:
                workspace = json.loads(workspace_result.stdout)
                current_desktop = int(workspace.get("id", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        windows = []
        for client in clients:
            at = client.get("at") or [-1, -1]
            size = client.get("size") or [-1, -1]
            workspace = client.get("workspace") or {}
            windows.append(self._normal_window(
                client.get("title") or client.get("class") or "unknown",
                client.get("title") or "",
                int(client.get("pid") or 0),
                int(workspace.get("id", 0)),
                [int(at[0]), int(at[1]), int(size[0]), int(size[1])],
                bool(client.get("hidden", False)),
            ))

        return self._snapshot(windows, active, current_desktop)

    def _walk_sway_nodes(self, node: dict[str, Any], workspace_num: int = 0) -> list[dict[str, Any]]:
        nodes = []
        if node.get("type") == "workspace":
            try:
                workspace_num = int(node.get("num", workspace_num))
            except (TypeError, ValueError):
                pass

        if node.get("type") == "con" and node.get("pid") is not None:
            node["pc_stats_workspace_num"] = workspace_num
            nodes.append(node)

        for child in node.get("nodes", []):
            nodes.extend(self._walk_sway_nodes(child, workspace_num))
        for child in node.get("floating_nodes", []):
            nodes.extend(self._walk_sway_nodes(child, workspace_num))

        return nodes

    def _get_windows_sway(self) -> WindowSnapshot | None:
        tree_result = self._run(["swaymsg", "-t", "get_tree", "-r"])
        if tree_result is None or tree_result.returncode != 0:
            return None

        try:
            tree = json.loads(tree_result.stdout)
        except json.JSONDecodeError as e:
            print(f"Invalid Sway tree data: {e}")
            return None

        current_desktop = 0
        workspace_result = self._run(["swaymsg", "-t", "get_workspaces", "-r"])
        if workspace_result is not None and workspace_result.returncode == 0:
            try:
                workspaces = json.loads(workspace_result.stdout)
                for workspace in workspaces:
                    if workspace.get("focused"):
                        current_desktop = int(workspace.get("num", 0))
                        break
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        windows = []
        active = ""
        for node in self._walk_sway_nodes(tree):
            app_id = node.get("app_id")
            props = node.get("window_properties") or {}
            name = node.get("name") or app_id or props.get("class") or "unknown"
            rect = node.get("rect") or {}
            geometry = [
                int(rect.get("x", -1)),
                int(rect.get("y", -1)),
                int(rect.get("width", -1)),
                int(rect.get("height", -1)),
            ]
            desktop = int(node.get("pc_stats_workspace_num", current_desktop))
            record = self._normal_window(
                name,
                node.get("name") or "",
                int(node.get("pid") or 0),
                desktop,
                geometry,
            )
            windows.append(record)

            if node.get("focused"):
                active = record["name"]

        return self._snapshot(windows, active, current_desktop)

    def get_windows(self) -> WindowSnapshot | None:
        match self.compositor:
            case Compositor.KDE_WAYLAND:
                data = self._get_windows_kde_wayland()
            case Compositor.X11:
                data = self._get_windows_x11()
            case Compositor.HYPRLAND:
                data = self._get_windows_hyprland()
            case Compositor.SWAY:
                data = self._get_windows_sway()
            case Compositor.GNOME_WAYLAND:
                print("GNOME Wayland window tracking requires a GNOME Shell extension.")
                return None
            case _:
                print("Window tracking is not supported on this desktop.")
                return None

        if not data:
            print("Couldn't retrieve window data")
            return None

        return data
