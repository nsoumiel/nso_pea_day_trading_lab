from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
import tomllib

UTC = timezone.utc
STEP = timedelta(minutes=5)
D = lambda value: Decimal(str(value))


def money(value):
    return D(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def timestamp(value):
    t = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Horodatage sans fuseau : utiliser UTC avec +00:00 ou Z')
    return t.astimezone(UTC)


@dataclass(frozen=True)
class Bar:
    symbol: str
    time: datetime  # start of completed 5-minute bar, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        values = [self.open, self.high, self.low, self.close, self.volume]
        if self.time.tzinfo is None or self.time.second or self.time.microsecond or self.time.minute % 5:
            raise ValueError('Bougie non alignée en 5 minutes ou sans fuseau')
        if not all(math.isfinite(x) for x in values):
            raise ValueError('OHLCV non fini')
        if min(values[:4]) <= 0 or self.volume < 0:
            raise ValueError('Prix ou volume invalide')
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError('OHLC incohérent')


@dataclass
class Config:
    capital: float = 5000
    max_trades_per_day: int = 2
    allocation: float = 1.0
    index_symbol: str = '^FCHI'
    rvol_days: int = 20
    rvol_threshold: float = 1.5
    ema_period: int = 20
    atr_period: int = 14
    atr_multiple: float = 1.5
    reward_multiple: float = 2.0
    slippage_bps: float = 5.0  # one-way cost, including half-spread
    exit_before_close_minutes: int = 10
    no_entry_before_close_minutes: int = 60
    max_participation: float = 0.01  # relative to PREVIOUS completed bar
    telegram_chat_id: str = '8910228694'
    poll_seconds: int = 300
    settlement_lag_minutes: int = 20  # delayed research feed, not real time
    symbols: tuple = ('TTE.PA', 'BNP.PA', 'AI.PA', 'MC.PA', 'OR.PA', 'SAN.PA',
                      'SU.PA', 'AIR.PA', 'SAF.PA', 'CS.PA', 'DG.PA', 'SGO.PA',
                      'CAP.PA', 'DSY.PA', 'LR.PA', 'KER.PA', 'ENGI.PA', 'ORA.PA',
                      'GLE.PA', 'ACA.PA')

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            raw = tomllib.load(f)
        unknown = set(raw) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f'Configuration inconnue : {unknown}')
        if 'symbols' in raw:
            raw['symbols'] = tuple(raw['symbols'])
        c = cls(**raw)
        if c.capital <= 0 or not 0 < c.allocation <= 1:
            raise ValueError('Capital/allocation invalide')
        if c.max_trades_per_day < 1 or c.rvol_days < 1 or c.atr_period < 1 or c.ema_period < 2:
            raise ValueError('Période/limite invalide')
        if not 0 <= c.slippage_bps < 100 or not 0 < c.max_participation <= 1:
            raise ValueError('Coûts/participation invalides')
        if c.atr_multiple <= 0 or c.reward_multiple <= 0 or c.rvol_threshold <= 0:
            raise ValueError('Seuils invalides')
        if c.exit_before_close_minutes < 5 or c.no_entry_before_close_minutes <= c.exit_before_close_minutes:
            raise ValueError('Horaires de clôture invalides')
        if c.poll_seconds < 60 or c.settlement_lag_minutes < 0:
            raise ValueError('Collecte trop fréquente ou délai invalide')
        if not c.symbols or len(set(c.symbols)) != len(c.symbols) or c.index_symbol in c.symbols:
            raise ValueError('Univers invalide')
        return c
