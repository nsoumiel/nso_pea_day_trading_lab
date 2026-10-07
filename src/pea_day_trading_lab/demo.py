"""Deterministic SYNTHETIC fixture; never a performance claim about real equities."""
from datetime import datetime,timedelta
from .models import Bar,UTC,STEP


def seed(store):
    bars, sessions = [], {}
    day = datetime(2025,1,6,9,tzinfo=UTC)
    n = 0
    while n < 26:
        if day.weekday() < 5:
            opening = day.replace(hour=8)  # 09:00 Paris in winter
            sessions[day.date().isoformat()] = (opening,opening+timedelta(hours=8,minutes=30))
            for slot in range(102):
                for symbol,base in [('TTE.PA',60),('BNP.PA',80),('^FCHI',7500)]:
                    p = base * (1 + slot*.00002)
                    if n >= 20 and slot >= 4: p += base*.004
                    v = 100000*(3 if n >= 20 else 1)
                    bars.append(Bar(symbol,opening+slot*STEP,p,p+base*.0002,p-base*.0002,p+base*.00005,v))
            n += 1
        day += timedelta(days=1)
    store.put_sessions(sessions)
    return store.put_bars(bars,'synthetic')
