"""Single chronological portfolio. Signals at close; fills next bar open."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from .models import D, money, STEP
from .costs import brokerage, max_quantity, ttf
from .strategy import Features, OpeningRangeStrategy


class DataGapError(ValueError):
    pass


class Engine:
    def __init__(self, config, calendar, trade_start=None):
        self.c, self.cal, self.trade_start = config, calendar, trade_start
        self.strategy = OpeningRangeStrategy(config)
        self.features = {s: Features(config) for s in (*config.symbols, config.index_symbol)}
        self.cash = money(config.capital)
        self.position = None
        self.pending = None
        self.events = []
        self.trades = []
        self.equity = []
        self.fees = Decimal('0.00')
        self.counts = defaultdict(int)
        self.last_time = None
        self.last_price = None
        self.last_position_bar = None

    def emit(self, t, kind, **payload):
        self.events.append({'time':t.isoformat(), 'kind':kind, **payload})

    def fill_price(self, price, side):
        return D(price) * (1 + D(self.c.slippage_bps) / 10000 * (1 if side == 'BUY' else -1))

    def enter(self, b, signal):
        p = self.fill_price(b.open, 'BUY')
        q = max_quantity(self.cash, p, self.c.allocation)
        if q < 1 or q > signal['volume'] * self.c.max_participation:
            self.emit(b.time, 'REJECTED', symbol=b.symbol, reason='cash_or_previous_bar_liquidity')
            return
        distance = D(signal['atr']) * D(self.c.atr_multiple)
        if distance >= p:
            self.emit(b.time, 'REJECTED', symbol=b.symbol, reason='invalid_stop')
            return
        gross = money(q*p); fee = brokerage(gross)
        self.cash -= gross + fee; self.fees += fee
        self.position = {'symbol':b.symbol, 'qty':q, 'entry':str(p), 'entry_time':b.time.isoformat(),
                         'cost':str(gross+fee), 'entry_fee':str(fee),
                         'stop':str(p-distance), 'target':str(p+distance*D(self.c.reward_multiple))}
        self.counts[b.time.date().isoformat()] += 1
        self.last_position_bar = b.time
        self.emit(b.time, 'BUY', **self.position, cash=str(self.cash),
                  estimated_stop_loss=str(money(q*distance + fee + brokerage(q*(p-distance)))))

    def exit(self, b, raw_price, reason):
        pos = self.position
        p = self.fill_price(raw_price, 'SELL')
        gross = money(pos['qty'] * p); fee = brokerage(gross)
        pnl = gross - fee - D(pos['cost'])
        self.cash += gross - fee; self.fees += fee
        tax = ttf([(pos['qty'],pos['entry'])],pos['qty'],b.time.date())
        trade = {**pos, 'exit':str(p), 'exit_time':b.time.isoformat(), 'exit_fee':str(fee),
                 'pnl':str(pnl), 'ttf':str(tax), 'reason':reason}
        self.trades.append(trade)
        self.emit(b.time, 'SELL', **trade, cash=str(self.cash))
        self.position = None; self.last_position_bar = None

    def on_bars(self, t, group):
        current = {b.symbol:b for b in group if b.symbol in self.features and self.cal.slot(t) is not None}
        if not current:
            return
        cutoff, liquidate = self.cal.deadlines(t, self.c)
        if self.position:
            p = self.position
            if t.date() != self.last_position_bar.date():
                raise DataGapError('Position non liquidée avant la fin de séance : résultats invalides')
            if t > self.last_position_bar + STEP and p['symbol'] not in current:
                raise DataGapError('Bougie manquante pendant une position : exécution inconnue')
        if self.pending:
            signal = self.pending; self.pending = None
            b = current.get(signal['symbol'])
            if (b and t == signal['time'] + STEP and t < cutoff and not self.position
                    and self.counts[t.date().isoformat()] < self.c.max_trades_per_day):
                self.enter(b, signal)
            else:
                self.emit(t,'REJECTED',symbol=signal['symbol'],reason='next_bar_missing_or_entry_cutoff')
        if self.position:
            b = current.get(self.position['symbol'])
            if b:
                if self.last_position_bar and t > self.last_position_bar + STEP:
                    raise DataGapError('Trou dans les données avec position ouverte')
                stop, target = D(self.position['stop']), D(self.position['target'])
                if t >= liquidate:
                    self.exit(b,b.open,'session_exit')
                elif D(b.open) <= stop:
                    self.exit(b,b.open,'gap_stop')
                elif D(b.open) >= target:
                    self.exit(b,target,'target')  # no optimistic gap price improvement
                elif D(b.low) <= stop:
                    self.exit(b,stop,'stop')  # pessimistic if both touched
                elif D(b.high) >= target:
                    self.exit(b,target,'target')
                else:
                    self.last_position_bar = t; self.last_price = b.close
        fs = {s:self.features[s].update(b,self.cal) for s,b in current.items()}
        index = current.get(self.c.index_symbol)
        candidates = []
        if (index and not self.position and t+STEP < cutoff
                and (self.trade_start is None or t+STEP >= self.trade_start)
                and self.counts[t.date().isoformat()] < self.c.max_trades_per_day):
            for s in self.c.symbols:
                b = current.get(s)
                if b and self.strategy.signal(b,fs.get(s),index,fs.get(self.c.index_symbol)):
                    f = fs[s]
                    candidates.append({'symbol':s,'time':t,'rvol':f['rvol'],
                                       'atr':f['atr'],'volume':b.volume})
                    self.emit(t+STEP,'SIGNAL',symbol=s,**f)
        if candidates:
            candidates.sort(key=lambda x:(-x['rvol'],x['symbol']))
            self.pending = candidates[0]
            for signal in candidates[1:]:
                self.emit(t+STEP,'REJECTED',symbol=signal['symbol'],reason='one_position_priority')
        equity = self.cash
        if self.position:
            b = current.get(self.position['symbol'])
            if b:
                self.last_price = b.close
            mark = self.fill_price(self.last_price,'SELL') * self.position['qty']
            equity += money(mark) - brokerage(mark)
        self.equity.append({'time':(t+STEP).isoformat(),'equity':str(equity)})
        self.last_time = t

    def run(self, bars):
        grouped = defaultdict(list)
        seen = set()
        for b in bars:
            key = (b.time,b.symbol)
            if key in seen:
                raise ValueError('Bougie en doublon dans le moteur')
            seen.add(key); grouped[b.time].append(b)
        for t in sorted(grouped):
            self.on_bars(t,grouped[t])
        return self.report()

    def report(self):
        pnls = [D(t['pnl']) for t in self.trades]
        wins = sum((x for x in pnls if x>0),Decimal(0))
        losses = -sum((x for x in pnls if x<0),Decimal(0))
        peak = D(self.c.capital); dd = Decimal(0); dd_pct = Decimal(0)
        for point in self.equity:
            value = D(point['equity']); peak = max(peak,value)
            dd = max(dd,peak-value)
            if peak: dd_pct = max(dd_pct,(peak-value)/peak*100)
        net = sum(pnls,Decimal(0))
        return {'mode':'PAPER_RESEARCH_ONLY','initial_capital':str(money(self.c.capital)),
                'cash':str(self.cash), 'equity':self.equity[-1]['equity'] if self.equity else str(self.cash),
                'closed_trades':len(pnls), 'realized_pnl_net':str(net),
                'closed_trades_pnl_before_fees':str(net + sum((D(t['entry_fee'])+D(t['exit_fee']) for t in self.trades),Decimal(0))),
                'brokerage_paid':str(self.fees), 'ttf_closed_trades':'0.00',
                'ttf_total':'0.00' if self.position is None else None,
                'win_rate_pct':100*sum(x>0 for x in pnls)/len(pnls) if pnls else None,
                'profit_factor':float(wins/losses) if losses else None,
                'profit_factor_note':'undefined_no_losses' if not losses else None,
                'average_pnl':str(money(net/len(pnls))) if pnls else None,
                'max_drawdown_eur':str(money(dd)), 'max_drawdown_pct':float(dd_pct),
                'flat':self.position is None, 'open_position':self.position,
                'data_end':self.last_time.isoformat() if self.last_time else None,
                'warning':'Portefeuille non liquidé : période incomplète, TTF totale non calculée' if self.position else None,
                'fees_model':'Bourse Direct current standard tariff applied to all dates',
                'slippage_bps_per_side':self.c.slippage_bps}
