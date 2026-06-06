from pcstats import Mouse, Collector

import time

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

def main():
    mouse = Mouse()

    last_update = 0
    while True:
        if int(time.time()) % 30 == 0 and last_update != int(time.time()):
            last_update = int(time.time())
            mouse.detect_mouse()

        click = mouse.poll()
        if click:
            store_click(click)


if __name__ == "__main__":
    main()
