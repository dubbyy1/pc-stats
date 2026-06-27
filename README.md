# PC Stats

![Dashboard Screenshot](images/dashboard.png)

PC Stats records mouse click and window activity on Linux and visualises it in a browser dashboard. The collector runs locally, writes data to a SQLite database, and the dashboard reads that database to show heatmaps, charts, and app usage statistics.

## What It Tracks

- Mouse click position across all detected monitors
- Click timestamp
- Click button: left, right, or middle
- Current monitor layout and monitor names
- Open application windows
- Active app and current desktop/workspace
- Window position and size snapshots

The collector writes data to:

```bash
~/.local/share/pc-stats/stats.db
```

Collector settings are stored at:

```bash
~/.local/share/pc-stats/config.yaml
```

The database contains:

- `clicks(id, timestamp, x, y, button)`
- `monitors(id, name, x, y, width, height)`
- `window_snapshots(id, timestamp, active, current_desktop)`
- `windows(ssid, name, pid, desktop, x, y, width, height)`

## Dashboard - `dashboard/`

The hosted dashboard is available at:

```text
https://pc-stats.dubbyy.com
```

Use **Import Data** and select your `stats.db` file. The dashboard runs in the browser using `sql.js`; imported databases are cached locally in the browser so the last imported file can be reopened automatically.

You can also load a database URL with the `db` query parameter:

```text
https://pc-stats.dubbyy.com?db=https://example.com/stats.db
```

An example database is included at:

```text
examples/stats.db
```

The dashboard currently includes:

- Click heatmap
- Timeline filtering
- Button filtering
- Button breakdown chart
- Monitor breakdown chart
- Hourly activity chart
- Daily activity chart
- Windows section
- App frequency, focus, and screen dominance statistics
- Window geometry visualisation
- Desktop/workspace breakdown

### Running The Dashboard Locally

From the `dashboard` directory:

```bash
npm install
npm run dev
```

Build the static dashboard with:

```bash
npm run build
```

The static build is written to:

```bash
dashboard/build
```

## Collector - `collector/`

![Collector Screenshot](images/collector.png)

The collector runs in the background to collect the data. It also has a small status window.

The status window shows pending/stored clicks, the current mouse device, the last active app, and the number of window snapshots taken. It also includes:

- Snapshot interval setting
- Pause/resume tracking
- Stop button

### Platform Support

Due to the low-level nature of the input monitoring, the collector is Linux only.

| Platform | Status |
|---|---|
| KDE Wayland | Supported |
| X11 | Supported |
| GNOME Wayland | Partial |
| Hyprland | Partial |
| Sway | Partial |
| Other | Unsupported |

KDE Wayland uses KWin scripting for window data. X11 uses Xlib/EWMH window properties. Hyprland uses `hyprctl`. Sway uses `swaymsg`. GNOME Wayland has limited support because global window information generally requires a GNOME Shell extension.

### First-Time Setup

The collector needs permission to read input devices. Add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

Log out and back in after running that command.

Some systems may also require `python-xlib`, PyYAML, and Qt/PySide runtime dependencies for source builds.

### Running From Source

Clone the repository and install collector dependencies:

```bash
git clone https://github.com/dubbyy1/pc-stats.git
cd pc-stats/collector
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Building The Collector

From the `collector` directory:

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller main.py --onefile --name pc-stats
```

The binary will be created at:

```bash
collector/dist/pc-stats
```

Run it with:

```bash
./dist/pc-stats
```
