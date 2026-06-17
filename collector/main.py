from pcstats import Mouse, Database

import sys
import signal
import threading
import time
import queue
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton

mouse = Mouse()
click_queue: queue.Queue[tuple[float, int, int, str]] = queue.Queue()
click_buffer: list[tuple[float, int, int, str]] = []
db = Database()

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
    clicks = click_queue.qsize()
    while not click_queue.empty():
        ts, x, y, button = click_queue.get()
        click_buffer.append((ts, x, y, button))

    if not click_buffer:
        return

    print(f"Storing {clicks} Clicks...")
    db.store_clicks(click_buffer)
    click_buffer.clear()

    return clicks

def ui():
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
    layout.addWidget(last_write)
    layout.addWidget(clicks_pending)
    layout.addWidget(clicks_stored)
    layout.addWidget(mouse_name)

    stop = QPushButton("Stop")
    layout.addWidget(stop)
    _ = stop.clicked.connect(app.exit)

    def update():
        last_write.setText(f"Last write: {time.strftime("%H:%M:%S")}")
        clicks_stored.setText(f"Clicks stored: {drain_clicks()}")

    def refresh():
        clicks_pending.setText(f"Clicks pending: {click_queue.qsize()}")
        mouse_name.setText(f"Mouse: {", ".join(mouse.get_names())}")

    update_timer = QTimer()
    _ =  update_timer.timeout.connect(update)
    update_timer.start(300_000)

    refresh_timer = QTimer()
    _ =  refresh_timer.timeout.connect(refresh)
    refresh_timer.start(100)

    window.show()

    return(app.exec())

if __name__ == "__main__":
    threading.Thread(target=collect_clicks, daemon=True, args=(mouse, click_queue)).start()
    db.store_monitors(get_monitors())

    res = ui()
    print()

    drain_clicks()
    db.close()

    sys.exit(res)
