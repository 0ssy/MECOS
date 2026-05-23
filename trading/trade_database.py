import sqlite3
from typing import Dict, Any, List
from loguru import logger
from datetime import datetime

class TradeDatabase:
    def __init__(self, db_path: str = 'data/trading.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._initialize_schema()
        logger.info(f'Trade Database initialized: {db_path}')

    def _initialize_schema(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            side TEXT,
            size REAL,
            price REAL,
            status TEXT,
            timestamp TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            symbol TEXT,
            size REAL,
            price REAL,
            timestamp TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            signal TEXT,
            confidence REAL,
            regime TEXT,
            features TEXT,
            timestamp TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_value REAL,
            cash REAL,
            positions TEXT,
            timestamp TEXT
        )
        ''')
        
        self.conn.commit()

    def insert_order(self, order: Dict) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO orders (symbol, side, size, price, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            order['symbol'],
            order['side'],
            order['size'],
            order['price'],
            order.get('status', 'CREATED'),
            datetime.now().isoformat()
        ))
        self.conn.commit()
        return cursor.lastrowid

    def insert_fill(self, fill: Dict):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO fills (order_id, symbol, size, price, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            fill['order_id'],
            fill['symbol'],
            fill['size'],
            fill['price'],
            datetime.now().isoformat()
        ))
        self.conn.commit()

    def insert_signal(self, signal: Dict):
        import json
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO signals (symbol, signal, confidence, regime, features, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            signal['symbol'],
            signal['signal'],
            signal['confidence'],
            signal.get('regime', ''),
            json.dumps(signal.get('features', {})),
            datetime.now().isoformat()
        ))
        self.conn.commit()

    def save_portfolio_snapshot(self, portfolio: Dict):
        import json
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO portfolio_snapshots (total_value, cash, positions, timestamp)
        VALUES (?, ?, ?, ?)
        ''', (
            portfolio['total_value'],
            portfolio['cash'],
            json.dumps(portfolio['positions']),
            datetime.now().isoformat()
        ))
        self.conn.commit()

    def get_recent_signals(self, limit: int = 100) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_performance_stats(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM fills')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT total_value FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1')
        current_value = cursor.fetchone()
        current_value = current_value[0] if current_value else 10000
        
        return {
            'total_trades': total_trades,
            'current_portfolio_value': current_value
        }
