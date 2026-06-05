from enum import Enum, auto
import os

class Compositor(Enum):
    X11 = auto()
    KDE_WAYLAND = auto()
    GNOME_WAYLAND = auto()
    HYPRLAND = auto()
    UNSUPPORTED = auto()


def detect_compositor() -> Compositor:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if session == "x11":
        return Compositor.X11
    if session == "wayland":
        if "kde" in desktop:
            return Compositor.KDE_WAYLAND
        if "gnome" in desktop:
            return Compositor.GNOME_WAYLAND
        if "hyprland" in desktop:
            return Compositor.HYPRLAND
    return Compositor.UNSUPPORTED
