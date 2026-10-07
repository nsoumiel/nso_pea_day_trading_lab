"""Causal indicators. RVOL compares the same slot across complete prior sessions."""
from collections import defaultdict, deque
from statistics import mean
from .models import STEP


class Features:
    def __init__(self, config):
        self.c = config
        self.ema = None
        self.previous_close = None
        self.tr = deque(maxlen=config.atr_period)
        self.n = 0
        self.history = deque(maxlen=config.rvol_days)
        self.day = None
        self.cur = {}
        self.last = None
        self.last_slot = -1
        self.valid = True
        self.volume = 0
        self.pv = 0
        self.range_high = 0
        self.open = 0
        self.crossed = False
        self.expected_slots = 0

    def update(self, b, calendar):
        slot = calendar.slot(b.time)
        if slot is None:
            return None
        day = calendar.bounds(b.time)[0].date()
        if day != self.day:
            if self.day is not None and self.valid and len(self.cur) == self.expected_slots:
                self.history.append(self.cur)
            self.day = day
            self.cur = {}; self.volume = 0; self.pv = 0; self.range_high = 0
            self.last_slot = -1; self.valid = True; self.crossed = False
            self.open = b.open
            bounds = calendar.bounds(b.time)
            self.expected_slots = int((bounds[1] - bounds[0]) / STEP)
        if slot != self.last_slot + 1:
            self.valid = False
        old_ema = self.ema
        self.ema = b.close if old_ema is None else old_ema + 2/(self.c.ema_period+1)*(b.close-old_ema)
        prev = self.previous_close if self.previous_close is not None else b.open
        self.tr.append(max(b.high-b.low, abs(b.high-prev), abs(b.low-prev)))
        self.previous_close = b.close; self.n += 1
        self.volume += b.volume
        self.pv += ((b.high+b.low+b.close)/3) * b.volume
        self.cur[slot] = self.volume
        if slot < 3:
            self.range_high = max(self.range_high, b.high)
        crossing = slot >= 3 and not self.crossed and b.close > self.range_high
        if slot >= 3:
            self.crossed = b.close > self.range_high
        reference = [h[slot] for h in self.history if slot in h]
        rvol = self.volume / mean(reference) if len(reference) == self.c.rvol_days and mean(reference) > 0 else None
        result = {'ready': self.valid and self.n >= max(self.c.ema_period, self.c.atr_period),
                  'slot': slot, 'crossing': crossing, 'ema': self.ema,
                  'rising': old_ema is not None and self.ema > old_ema,
                  'atr': mean(self.tr), 'vwap': self.pv/self.volume if self.volume else None,
                  'rvol': rvol, 'volume': b.volume, 'opening': self.open,
                  'range_high': self.range_high}
        self.last = b; self.last_slot = slot
        return result


class OpeningRangeStrategy:
    def __init__(self, config):
        self.c = config

    def signal(self, bar, feature, market_bar, market_feature):
        f, m = feature, market_feature
        if not f or not m or not f['ready'] or not m['ready']:
            return False
        return (f['crossing'] and f['vwap'] is not None and bar.close > f['vwap']
                and f['rvol'] is not None and f['rvol'] >= self.c.rvol_threshold
                and bar.close > f['ema'] and f['rising'] and f['atr'] > 0
                and market_bar.close > m['opening'] and market_bar.close > m['ema'])
