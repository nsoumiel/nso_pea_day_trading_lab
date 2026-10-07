"""Free sources and local CSV. Never bypass provider limits."""
import csv
import logging
import time
from datetime import datetime, timedelta
from .models import Bar, timestamp, UTC, STEP
from .calendar import xpar_sessions

LOG = logging.getLogger(__name__)


def load_csv(path):
    result = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            result.append(Bar(row['symbol'],timestamp(row['timestamp_utc']),
                *(float(row[k]) for k in ('open','high','low','close','volume'))))
    return result


def load_calendar_csv(path):
    with open(path,newline='',encoding='utf-8-sig') as f:
        return {r['date']:(timestamp(r['open_utc']),timestamp(r['close_utc'])) for r in csv.DictReader(f)}


def collect_yahoo(store, config, days=59):
    import yfinance as yf
    if not 1 <= days <= 59:
        raise ValueError('Yahoo 5m : demander entre 1 et 59 jours calendaires')
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    sessions = xpar_sessions(start.date().isoformat(),(now+timedelta(days=2)).date().isoformat())
    store.put_sessions(sessions)
    cal = store.calendar()
    stats = {}
    for symbol in (config.index_symbol,*config.symbols):
        try:
            frame = yf.Ticker(symbol).history(start=start, end=now, interval='5m',
                auto_adjust=False, back_adjust=False, actions=False, prepost=False,
                raise_errors=True, timeout=20)
            if frame.empty:
                raise ValueError('Aucune donnée retournée')
            bars = []
            cutoff = now - timedelta(minutes=config.settlement_lag_minutes)
            for dt, row in frame.iterrows():
                t = dt.to_pydatetime().astimezone(UTC)
                # Closed bars only, with an additional conservative finalization delay.
                if t+STEP > cutoff or cal.slot(t) is None:
                    continue
                try:
                    bars.append(Bar(symbol,t,*(float(row[k]) for k in ['Open','High','Low','Close','Volume'])))
                except ValueError:
                    LOG.warning('Bougie invalide ignorée %s %s',symbol,t)
            stats[symbol] = store.put_bars(bars,'yahoo')
        except Exception as exc:
            # Provider exceptions may contain URLs. Never include credentials in logs.
            LOG.error('Collecte échouée %s (%s), aucune donnée inventée',symbol,type(exc).__name__)
            stats[symbol] = None
            if 'rate' in type(exc).__name__.lower():
                LOG.error('Limite Yahoo : arrêt de la collecte, réessayer plus tard')
                break
        time.sleep(1)
    return stats
