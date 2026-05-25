# trading/equity_persistence.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'equity_curve.db')

class EquityPersistence:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS equity_curve (
            timestamp REAL,
            equity REAL,
            positions TEXT,
            trades TEXT,
            drawdown REAL,
            sharpe REAL,
            win_rate REAL
        )''')
        self.conn.commit()

    def save(self, timestamp, equity, positions, trades, drawdown, sharpe, win_rate):
        c = self.conn.cursor()
        c.execute('''INSERT INTO equity_curve VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (timestamp, equity, positions, trades, drawdown, sharpe, win_rate))
        self.conn.commit()

    def close(self):
        self.conn.close()
