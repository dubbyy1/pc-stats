# PC Stats

A tool that collects data about how you interact with your computer and presents it in a visual dashboard.

## Features

- **Click heatmap** — records every mouse click and its position on screen, visualised as a heatmap

More features are planned.

## Platform support

### Linux
| Platform | Status |
|---|---|
| KDE Wayland | ✅ Supported |
| X11 | Coming soon |
| GNOME Wayland | Coming soon |
| Hyprland | Coming soon |

## Installation

Download the latest binary from [Releases](../../releases).

### First-time setup

PC Stats reads raw input events from `/dev/input`, which requires your user to be in the `input` group. Run this once:

```bash
sudo usermod -aG input $USER
```

Then **log out and back in** for the change to take effect.

### Running

```bash
chmod +x pc-stats
./pc-stats
```

Data is stored at `~/.local/share/pc-stats/stats.db`.

## Building from source

```bash
git clone https://github.com/your-username/pc-stats
cd pc-stats/collector
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller main.py --onefile --name pc-stats
```

The binary will be at `dist/pc-stats`.
