import tempfile
import unittest
from datetime import date,datetime,timedelta
from pathlib import Path
from pea_day_trading_lab.models import Bar,Config,UTC,STEP,D,timestamp
from pea_day_trading_lab.costs import brokerage,max_quantity,ttf
from pea_day_trading_lab.calendar import Calendar
from pea_day_trading_lab.engine import Engine,DataGapError
from pea_day_trading_lab.strategy import Features
from pea_day_trading_lab.storage import Store
from pea_day_trading_lab.demo import seed
from pea_day_trading_lab.cli import simulate

T = datetime(2025,1,6,8,tzinfo=UTC)
def bar(t=T,s='TTE.PA',o=100,h=100.2,l=99.8,c=100,v=100000):
    return Bar(s,t,o,h,l,c,v)
def calendar():
    return Calendar({(T+timedelta(days=i)).date().isoformat():
        (T+timedelta(days=i),T+timedelta(days=i,hours=8,minutes=30)) for i in range(2)})
def signal(t=T):
    return {'time':t,'symbol':'TTE.PA','atr':1.0,'volume':100000,'rvol':2}

class AccountingTests(unittest.TestCase):
    def test_fee_boundaries_and_pea_cap(self):
        for n,want in [(100,'.50'),(198,'.99'),(500,'.99'),(500.01,'1.90'),(1000,'1.90'),
                       (1000.01,'2.90'),(2000,'2.90'),(2000.01,'3.80'),(4400,'3.80'),(4400.01,'3.96'),(5000,'4.50')]:
            with self.subTest(n=n): self.assertEqual(brokerage(n),D(want))
    def test_all_in_reserves_fee(self):
        q = max_quantity(5000,100)
        self.assertEqual(q,49)
        self.assertLessEqual(q*100+brokerage(q*100),5000)
        self.assertGreater((q+1)*100+brokerage((q+1)*100),5000)
    def test_ttf_netting(self):
        self.assertEqual(ttf([(30,100),(20,120)],50,date(2026,1,1)),D(0))
        self.assertEqual(ttf([(30,100),(20,120)],40,date(2026,1,1)),D('4.32'))
    def test_ttf_rates(self):
        self.assertEqual(ttf([(10,100)],0,date(2025,3,31)),D('3'))
        self.assertEqual(ttf([(10,100)],0,date(2025,4,1)),D('4'))
        self.assertEqual(ttf([(10,100)],0,date(2026,1,1),False),D(0))

class ExecutionTests(unittest.TestCase):
    def setUp(self): self.e = Engine(Config(slippage_bps=0,symbols=('TTE.PA',)),calendar())
    def test_next_bar_entry(self):
        self.e.pending = signal(); self.e.on_bars(T+STEP,[bar(T+STEP)])
        self.assertEqual(self.e.position['entry_time'],(T+STEP).isoformat())
        self.assertEqual(self.e.position['qty'],49)
        self.assertGreaterEqual(self.e.cash,0)
    def test_missing_next_bar_rejected(self):
        self.e.pending = signal(); self.e.on_bars(T+2*STEP,[bar(T+2*STEP)])
        self.assertIsNone(self.e.position)
        self.assertEqual(self.e.events[0]['kind'],'REJECTED')
    def test_stop_before_target(self):
        self.e.enter(bar(),signal()); self.e.on_bars(T+STEP,[bar(T+STEP,h=105,l=97)])
        self.assertEqual(self.e.trades[0]['reason'],'stop')
        self.assertEqual(D(self.e.trades[0]['exit']),D('98.5'))
    def test_gap_stop(self):
        self.e.enter(bar(),signal()); self.e.on_bars(T+STEP,[bar(T+STEP,o=90,h=92,l=89,c=91)])
        self.assertEqual(D(self.e.trades[0]['exit']),D(90))
    def test_trade_cap(self):
        self.e.counts[T.date().isoformat()] = 2
        self.e.pending = signal(); self.e.on_bars(T+STEP,[bar(T+STEP)])
        self.assertIsNone(self.e.position)
    def test_liquidity(self):
        s = signal(); s['volume'] = 10; self.e.enter(bar(),s)
        self.assertIsNone(self.e.position)
    def test_session_exit(self):
        t = T+timedelta(hours=8,minutes=20)
        self.e.enter(bar(t-STEP),signal()); self.e.on_bars(t,[bar(t)])
        self.assertTrue(self.e.report()['flat'])
        self.assertEqual(self.e.trades[0]['reason'],'session_exit')
        self.assertEqual(self.e.report()['ttf_total'],'0.00')
    def test_half_day_exit(self):
        t = T+timedelta(hours=5)
        self.e.cal = Calendar({T.date().isoformat():(T,t)})
        self.e.enter(bar(t-3*STEP),signal()); self.e.on_bars(t-2*STEP,[bar(t-2*STEP)])
        self.assertEqual(self.e.trades[0]['reason'],'session_exit')
    def test_no_fake_liquidation(self):
        self.e.enter(bar(),signal())
        self.assertFalse(self.e.report()['flat']); self.assertIsNone(self.e.report()['ttf_total'])
    def test_position_data_gap_invalid(self):
        self.e.enter(bar(),signal())
        with self.assertRaises(DataGapError): self.e.on_bars(T+2*STEP,[bar(T+2*STEP)])
    def test_cash_conservation(self):
        self.e.enter(bar(),signal()); self.e.exit(bar(T+STEP),100,'test')
        self.assertEqual(self.e.cash,D('4991.18'))
        self.assertEqual(self.e.report()['brokerage_paid'],'8.82')
        self.assertEqual(self.e.report()['realized_pnl_net'],'-8.82')

class DataTests(unittest.TestCase):
    def test_invalid_bars(self):
        with self.assertRaises(ValueError): bar(h=99)
        with self.assertRaises(ValueError): bar(v=-1)
        with self.assertRaises(ValueError): bar(c=float('nan'))
        with self.assertRaises(ValueError): timestamp('2026-10-07T09:00:00')
    def test_storage_idempotent_sources(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d)/'test.db')
            self.assertEqual(s.put_bars([bar()],'a'),1); self.assertEqual(s.put_bars([bar()],'a'),0)
            self.assertEqual(s.put_bars([bar()],'b'),1)
            self.assertEqual(len(s.bars('a',['TTE.PA'])),1); s.close()
    def test_dst(self):
        self.assertEqual(timestamp('2025-01-06T09:00:00+01:00').hour,8)
        self.assertEqual(timestamp('2025-07-07T09:00:00+02:00').hour,7)
    def test_missing_opening(self):
        f = Features(Config()); r = f.update(bar(T+STEP),calendar())
        self.assertFalse(r['ready']); self.assertFalse(f.valid)
    def test_rvol_prior_same_slot(self):
        f = Features(Config(rvol_days=1)); cal = calendar()
        for slot in range(102): f.update(bar(T+slot*STEP,v=100),cal)
        self.assertEqual(f.update(bar(T+timedelta(days=1),v=300),cal)['rvol'],3)
    def test_full_demo_reproducible_and_flat(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d)/'test.db'); seed(s); c = Config(symbols=('TTE.PA','BNP.PA'))
            e,r,bars = simulate(s,c,'synthetic')
            self.assertGreater(r['closed_trades'],0); self.assertTrue(r['flat'])
            self.assertTrue(all(n<=2 for n in e.counts.values()))
            self.assertTrue(all(t['entry_time'][:10]==t['exit_time'][:10] for t in e.trades))
            ee,rr,_ = simulate(s,c,'synthetic'); self.assertEqual(e.trades,ee.trades); self.assertEqual(r,rr)
            cut = bars[-600].time; prefix = [b for b in bars if b.time<cut]
            pe = Engine(c,s.calendar()); pe.run(prefix)
            self.assertEqual(pe.trades,e.trades[:len(pe.trades)]); s.close()

if __name__ == '__main__': unittest.main()
