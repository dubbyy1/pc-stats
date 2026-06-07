from pcstats import Mouse, Collector

import time
import threading

collector = Collector()
click_buffer: list[tuple[float, int, int, str]] = []

def store_click(click: tuple[int, int, str]):
    global click_buffer
    x, y, button = click
    click_buffer.append((time.time(), x, y, button))

    if len(click_buffer) >= 10:
        print("Storing Clicks...")
        collector.store_clicks(click_buffer)
        click_buffer = []

def clicks(mouse:Mouse):
    mouse = Mouse()

    for click in mouse.test():
        store_click(click)

def main():
    mouse = Mouse()
    threading.Thread(target=clicks, daemon=True, args=(mouse,)).start()

    while True:
        # more features coming soon

        time.sleep(30)

if __name__ == "__main__":
    main()
