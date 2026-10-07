import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from .models import Bar, timestamp, UTC
from .calendar import Calendar


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES(1);
        CREATE TABLE IF NOT EXISTS bars(
          source TEXT, symbol TEXT, time TEXT, open REAL, high REAL, low REAL,
          close REAL, volume REAL, received TEXT,
          PRIMARY KEY(source,symbol,time));
        CREATE TABLE IF NOT EXISTS sessions(day TEXT PRIMARY KEY, opening TEXT, closing TEXT);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, mode TEXT, config TEXT,
          created TEXT, report TEXT, state TEXT);
        CREATE TABLE IF NOT EXISTS events(run TEXT, seq INTEGER, time TEXT,
          kind TEXT, payload TEXT, PRIMARY KEY(run,seq));
        CREATE TABLE IF NOT EXISTS notifications(key TEXT PRIMARY KEY, text TEXT,
          sent TEXT, attempts INTEGER DEFAULT 0);
        ''')

    def put_bars(self, bars, source):
        now = datetime.now(UTC).isoformat()
        before = self.db.total_changes
        # Immutable first observation: never silently rewrite a past simulated bar.
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO bars VALUES(?,?,?,?,?,?,?,?,?)',
                [(source,b.symbol,b.time.isoformat(),b.open,b.high,b.low,b.close,b.volume,now) for b in bars])
        return self.db.total_changes - before

    def bars(self, source, symbols, start=None, end=None):
        query = 'SELECT symbol,time,open,high,low,close,volume FROM bars WHERE source=?'
        args = [source]
        query += ' AND symbol IN (' + ','.join('?' for _ in symbols) + ')'
        args.extend(symbols)
        if start:
            query += ' AND time>=?'; args.append(start)
        if end:
            query += ' AND time<?'; args.append(end)
        query += ' ORDER BY time,symbol'
        return [Bar(r[0],timestamp(r[1]),*r[2:]) for r in self.db.execute(query,args)]

    def put_sessions(self, sessions):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO sessions VALUES(?,?,?)',
                [(d,o.isoformat(),c.isoformat()) for d,(o,c) in sessions.items()])

    def calendar(self):
        return Calendar({d:(timestamp(o),timestamp(c)) for d,o,c in self.db.execute('SELECT * FROM sessions')})

    def save_run(self, run_id, mode, config, report, state, events):
        with self.db:
            self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET report=excluded.report,state=excluded.state',
                (run_id,mode,json.dumps(asdict(config)),datetime.now(UTC).isoformat(),
                 json.dumps(report),json.dumps(state)))
            self.db.execute('DELETE FROM events WHERE run=?',(run_id,))
            self.db.executemany('INSERT INTO events VALUES(?,?,?,?,?)',
                [(run_id,i,e['time'],e['kind'],json.dumps(e)) for i,e in enumerate(events)])

    def enqueue(self, key, text):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO notifications(key,text) VALUES(?,?)',(key,text))

    def close(self):
        self.db.close()
