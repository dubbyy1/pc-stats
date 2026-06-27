from pcstats import Mouse, Database, Windows

import yaml
import os
import sys
import threading
import time
import queue
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox

mouse = Mouse()
windows = Windows()
db = Database()
click_queue: queue.Queue[tuple[float, int, int, str]] = queue.Queue()
click_buffer: list[tuple[float, int, int, str]] = []

def get_monitors() -> list[tuple[int, str, int, int, int, int]]:
    app = QGuiApplication(sys.argv)

    res = [
        (
            id,
            screen.name(),
            screen.geometry().x(),
            screen.geometry().y(),
            screen.geometry().width(),
            screen.geometry().height()
        ) for id, screen in enumerate(app.screens())
    ]
    app.shutdown()
    return res

def collect_clicks(m: Mouse, queue: queue.Queue[tuple[float, int, int, str]]):
    for click in m.poll():
        queue.put(click)

def drain_clicks():
    click_count = click_queue.qsize()
    while not click_queue.empty():
        ts, x, y, button = click_queue.get()
        click_buffer.append((ts, x, y, button))

    if not click_buffer:
        return 0

    print(f"Storing {click_count} Clicks...")
    db.store_clicks(click_buffer)
    click_buffer.clear()

    return click_count

def ui(config:dict):
    app = QApplication([])

    window = QWidget()
    window.setWindowTitle("PC Stats")
    window.setWindowIcon(QIcon("assets/icon.png"))
    layout = QVBoxLayout(window)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    last_write = QLabel(f"Last write: {"00:00:00"}")
    clicks_stored = QLabel("Clicks stored: 0")
    clicks_pending = QLabel("Clicks pending: 0")
    mouse_name = QLabel("Mouse: unkown")
    window_snapshots = QLabel("Window snapshots taken: 0")
    active_window = QLabel("Last active window: unkown")
    layout.addWidget(last_write)
    layout.addWidget(clicks_pending)
    layout.addWidget(clicks_stored)
    layout.addWidget(mouse_name)
    layout.addWidget(window_snapshots)
    layout.addWidget(active_window)

    stepper_row = QHBoxLayout()
    stepper_row.setSpacing(5)
    layout.addLayout(stepper_row)

    def change_delay(value):
        global update_delay
        config["update_delay"] = value
        update_timer.setInterval(config["update_delay"] * 1000)

    delay_label = QLabel("Snapshot interval:")
    stepper_row.addWidget(delay_label)

    delay_stepper = QSpinBox()
    delay_stepper.setMaximum(3600)
    delay_stepper.setMinimum(10)
    delay_stepper.setValue(config["update_delay"])
    delay_stepper.setSuffix("s")
    stepper_row.addWidget(delay_stepper)
    _ = delay_stepper.valueChanged.connect(change_delay)

    def pause():
        mouse.pause()
        update_timer.stop()
        pause_button.setText("Resume")
        _ = pause_button.clicked.connect(resume)

    def resume():
        mouse.resume()
        update_timer.start()
        pause_button.setText("Pause")
        _ = pause_button.clicked.connect(pause)

    pause_button = QPushButton("Pause")
    layout.addWidget(pause_button)
    _ = pause_button.clicked.connect(pause)

    stop = QPushButton("Stop")
    layout.addWidget(stop)
    _ = stop.clicked.connect(app.exit)


    def update():
        active_window.setText("Updating...")
        window_snapshots.setText("Updating...")
        window_data = None
        while window_data is None:
            window_data = db.store_windows(windows.get_windows())
            if window_data:
                active_window.setText(f"Last active window: {window_data['last_active_window']}")
                window_snapshots.setText(f"Window snapshots taken: {window_data['window_snapshots']}")
                break
            time.sleep(2)

        last_write.setText(f"Last write: {time.strftime("%H:%M:%S")}")

        total_clicks = int(clicks_stored.text().split(" ")[-1])
        total_clicks += drain_clicks()
        clicks_stored.setText(f"Clicks stored: {total_clicks}")

    def refresh():
        clicks_pending.setText(f"Clicks pending: {click_queue.qsize()}")
        mouse_name.setText(f"Mouse: {", ".join(mouse.get_names())}")

    update_timer = QTimer()
    _ =  update_timer.timeout.connect(update)
    update_timer.start(config["update_delay"] * 1000)

    refresh_timer = QTimer()
    _ =  refresh_timer.timeout.connect(refresh)
    refresh_timer.start(100)

    window.show()
    update()

    return (app.exec(), config)

def main():
    config_path = os.path.expanduser("~/.local/share/pc-stats/config.yaml")
    config = {}
    try:
        with open(config_path, 'x') as f:
            f.write("update_delay: 300\nblocked_apps: []")
    except FileExistsError:
        pass

    config = yaml.load(open(config_path, 'r'), Loader=yaml.FullLoader)

    threading.Thread(target=collect_clicks, daemon=True, args=(mouse, click_queue)).start()
    db.store_monitors(get_monitors())

    res = ui(config)
    print()

    yaml.dump(config, open(config_path, 'w'))

    drain_clicks()
    db.store_windows(windows.get_windows())
    db.close()

    sys.exit(res[0])

if __name__ == "__main__":
    # windows.test()
    main()
