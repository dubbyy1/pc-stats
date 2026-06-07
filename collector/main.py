from pcstats import Mouse, Collector

import time
import threading
import queue

collector = Collector()

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

if __name__ == "__main__":
    main()
