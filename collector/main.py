from pcstats import Mouse, Collector

import time
import threading
import queue

from PySide6.QtGui import QGuiApplication
import sys

collector = Collector()

def get_monitors():
    app = QGuiApplication(sys.argv)

    return [
        (
            screen.name(),
            screen.geometry().x(),
            screen.geometry().y(),
            screen.geometry().width(),
            screen.geometry().height()
        ) for screen in app.screens()
    ]

def store_click(click: tuple[int, int, str]):
    global click_buffer
    x, y, button = click
    click_buffer.append((time.time(), x, y, button))

    if len(click_buffer) >= 10:
        print("Storing Clicks...")
        collector.store_clicks(click_buffer)
        click_buffer = []
def clicks(mouse:Mouse, queue: queue.Queue[tuple[float, int, int, str]]):
    for click in mouse.poll():
        queue.put(click)

def main():
    mouse = Mouse()
    click_queue: queue.Queue[tuple[float, int, int, str]] = queue.Queue()
    click_buffer: list[tuple[float, int, int, str]] = []
    threading.Thread(target=clicks, daemon=True, args=(mouse, click_queue)).start()

    collector.store_monitors(get_monitors())

    try:
        while True:
            # more features coming soon

            while not click_queue.empty():
                ts, x, y, button = click_queue.get()
                click_buffer.append((ts, x, y, button))
            if len(click_buffer) >= 10:
                print("Storing Clicks...")
                collector.store_clicks(click_buffer)
                click_buffer = []

            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        if click_buffer:
            print("Storing buffered clicks...")
            collector.store_clicks(click_buffer)
        collector.close()

if __name__ == "__main__":
    main()
