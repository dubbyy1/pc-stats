import os
import sqlite3

class Collector:
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
        self.conn.commit()

    def store_clicks(self, buffer:list[tuple[float, int,int,str]]):
        _ = self.conn.executemany(
            """
            INSERT INTO clicks (timestamp, x, y, button)
            VALUES (?, ?, ?, ?)
            """,
            buffer
        )
        self.conn.commit()
