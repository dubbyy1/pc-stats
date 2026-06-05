from pcstats import Mouse, Collector

import time

def main():
    collector = Collector()

    mouse = Mouse()
    click_buffer: list[tuple[float, int, int, str]] = []

    while True:
        if mouse.device:
            click = mouse.poll()
            if click:
                x, y, button = click
                click_buffer.append((time.time(), x, y, button))
                if len(click_buffer) >= 10:
                    print("Storing Clicks...")
                    collector.store_clicks(click_buffer)
                    click_buffer = []
        else:
            mouse.device = mouse.detect_mouse()


if __name__ == "__main__":
    main()
