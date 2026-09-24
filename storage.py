from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

class Store:
    def __init__(self, path: str):
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.con=sqlite3.connect(path, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.init()
    def init(self):
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS prices(
          symbol TEXT PRIMARY KEY, price REAL, change_pct REAL, change_abs REAL,
          received_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS state(
          symbol TEXT PRIMARY KEY, last_signal TEXT NOT NULL DEFAULT 'WAIT',
          last_kline_open INTEGER, last_received_at REAL
        );
        CREATE TABLE IF NOT EXISTS sent_notifications(
          symbol TEXT NOT NULL, kline_open INTEGER NOT NULL, direction TEXT NOT NULL,
          sent_at REAL NOT NULL, delayed INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(symbol,kline_open,direction)
        );
        CREATE TABLE IF NOT EXISTS processed_klines(
          symbol TEXT NOT NULL, kline_open INTEGER NOT NULL, signal TEXT NOT NULL,
          processed_at REAL NOT NULL, PRIMARY KEY(symbol,kline_open)
        );
        """)
        self.con.commit()
    def upsert_price(self,symbol,price,change_pct,change_abs,received_at):
        self.con.execute("INSERT INTO prices VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET price=excluded.price,change_pct=excluded.change_pct,change_abs=excluded.change_abs,received_at=excluded.received_at",(symbol,price,change_pct,change_abs,received_at)); self.con.commit()
    def get_state(self,symbol):
        return self.con.execute("SELECT last_signal,last_kline_open,last_received_at FROM state WHERE symbol=?",(symbol,)).fetchone()
    def set_state(self,symbol,signal,kline_open,received_at):
        self.con.execute("INSERT INTO state(symbol,last_signal,last_kline_open,last_received_at) VALUES(?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET last_signal=excluded.last_signal,last_kline_open=excluded.last_kline_open,last_received_at=excluded.last_received_at",(symbol,signal,kline_open,received_at)); self.con.commit()
    def was_sent(self,symbol,kline_open,direction):
        return self.con.execute("SELECT 1 FROM sent_notifications WHERE symbol=? AND kline_open=? AND direction=?",(symbol,kline_open,direction)).fetchone() is not None
    def mark_sent(self,symbol,kline_open,direction,sent_at,delayed):
        self.con.execute("INSERT OR IGNORE INTO sent_notifications VALUES(?,?,?,?,?)",(symbol,kline_open,direction,sent_at,int(delayed))); self.con.commit()
    def mark_processed(self,symbol,kline_open,signal,processed_at):
        self.con.execute("INSERT OR REPLACE INTO processed_klines VALUES(?,?,?,?)",(symbol,kline_open,signal,processed_at)); self.con.commit()
    def last_processed(self,symbol):
        row=self.con.execute("SELECT MAX(kline_open) FROM processed_klines WHERE symbol=?",(symbol,)).fetchone(); return row[0] if row else None
    def close(self): self.con.close()
