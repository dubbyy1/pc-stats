import os
import sqlite3

from time import time

class Database:
    def __init__(self):
        self.path:str = os.path.expanduser("~/.local/share/pc-stats")
        os.makedirs(self.path, exist_ok=True)
        self.conn: sqlite3.Connection = sqlite3.connect(os.path.join(self.path, "stats.db"))

        _ = self.conn.execute("PRAGMA journal_mode=WAL")

        _ = self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL    NOT NULL,
                x           INTEGER NOT NULL,
                y           INTEGER NOT NULL,
                button      STRING  NOT NULL
            )
            """
        )

        _ = self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY,
                name        STRING  NOT NULL,
                x           INTEGER NOT NULL,
                y           INTEGER NOT NULL,
                width       INTEGER NOT NULL,
                height      INTEGER NOT NULL
            )
            """
        )

        _ = self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS window_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL    NOT NULL,
                active_pid      INTEGER NOT NULL,
                current_desktop INTEGER NOT NULL
            )
            """
        )

        _ = self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS windows (
                ssid        INTEGER NOT NULL,
                name        STRING  NOT NULL,
                pid         INTEGER NOT NULL,
                desktop     INTEGER NOT NULL,
                x           INTEGER NOT NULL,
                y           INTEGER NOT NULL,
                width       INTEGER NOT NULL,
                height      INTEGER NOT NULL
            )
            """
        )

        self.conn.commit()

    def close(self):
        print("Closing DB...")
        self.conn.close()
        print("DB Closed.")

    def store_clicks(self, buffer:list[tuple[float, int,int,str]]):
        _ = self.conn.executemany(
            """
            INSERT INTO clicks (timestamp, x, y, button)
            VALUES (?, ?, ?, ?)
            """,
            buffer
        )
        self.conn.commit()

    # monitor = (id, name, x, y, width, height)
    def store_monitors(self, monitors:list[tuple[int,str,int,int,int,int]]):
        _ = self.conn.execute("DELETE FROM monitors")
        _ = self.conn.executemany(
            """
            INSERT INTO monitors (id, name, x, y, width, height)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            monitors
        )
        self.conn.commit()

    def store_windows(self, data):
        if not data:
            return None
        window_snapshot_id:int = self.conn.execute("SELECT MAX(id) FROM window_snapshots").fetchone()[0]
        if not window_snapshot_id:
            window_snapshot_id = 0
        print()

        snapshot:dict[str,int] = data["snapshot"]
        _ = self.conn.execute(
            """
            INSERT INTO window_snapshots (timestamp, active_pid, current_desktop)
            VALUES (?, ?, ?)
            """,
            (time(), snapshot["active_pid"], snapshot["current_desktop"])
        )

        window_res:list[list[int|str]] = []
        windows = data["windows"]
        for window in windows:
            geometry:list[int] = []
            if window["minimized"]:
                geometry = [-1, -1, -1, -1]
            else:
                geometry = [
                    window["geometry"][0],
                    window["geometry"][1],
                    window["geometry"][2],
                    window["geometry"][3],
                ]
            res:list[int|str] = [
                window_snapshot_id,
                window["name"],
                window["pid"],
                window["desktop"]
            ]
            res.extend(geometry)
            window_res.append(res)

        _ = self.conn.executemany(
            """
            INSERT INTO windows (ssid, name, pid, desktop, x, y, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            window_res
        )

        self.conn.commit()

        last_active_window = self.conn.execute("SELECT name FROM windows WHERE pid = ?", (snapshot["active_pid"],)).fetchone()[0]
        return {
            "last_active_window": last_active_window,
            "window_snapshots": window_snapshot_id,
        }
