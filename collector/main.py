from pcstats import Mouse, Collector

import sys
import signal
import threading
import time
import queue

from PySide6.QtGui import QGuiApplication

collector = Collector()

def get_monitors() -> list[tuple[int, str, int, int, int, int]]:
    app = QGuiApplication(sys.argv)

    return [
        (
            id,
            screen.name(),
            screen.geometry().x(),
            screen.geometry().y(),
            screen.geometry().width(),
            screen.geometry().height()
        ) for id, screen in enumerate(app.screens())
    ]

def clicks(mouse:Mouse, queue: queue.Queue[tuple[float, int, int, str]]):
    for click in mouse.poll():
        queue.put(click)

def drain_clicks(q, buf):
    while not q.empty():
        ts, x, y, button = q.get()
        buf.append((ts, x, y, button))
    if len(buf) >= 10:
        print("Storing Clicks...")
        collector.store_clicks(buf)

    return q, buf

def main():
    mouse = Mouse()
    click_queue: queue.Queue[tuple[float, int, int, str]] = queue.Queue()
    click_buffer: list[tuple[float, int, int, str]] = []
    threading.Thread(target=clicks, daemon=True, args=(mouse, click_queue)).start()

    collector.store_monitors(get_monitors())

    try:
        while True:
            # more features coming soon
            click_queue, click_buffer = drain_clicks(click_queue, click_buffer)
            time.sleep(300)
    except KeyboardInterrupt:
        pass
    finally:
        _ = signal.signal(signal.SIGINT, signal.SIG_IGN)

        click_queue, click_buffer = drain_clicks(click_queue, click_buffer)
        try:
            collector.close()
        except KeyboardInterrupt:
            pass
        print("Exiting.")

if __name__ == "__main__":
    main()
