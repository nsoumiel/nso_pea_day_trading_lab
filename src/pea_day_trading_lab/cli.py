import argparse
import csv
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import asdict
from datetime import datetime,timedelta
from pathlib import Path
import time
import uuid
from zoneinfo import ZoneInfo

from . import __version__
from .models import Config, UTC, STEP, timestamp
from .storage import Store
from .providers import load_csv,load_calendar_csv,collect_yahoo
from .engine import Engine
from .notifications import Telegram,load_env

LOG = logging.getLogger(__name__)


def setup_logging():
    Path('data').mkdir(exist_ok=True)
    handler = RotatingFileHandler('data/pea-lab.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[handler,logging.StreamHandler()])


def fingerprint(bars):
    h = hashlib.sha256()
    for b in bars:
        h.update(repr(b).encode())
    return h.hexdigest()


def write_report(engine, report, directory):
    out = Path(directory); out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    for name,rows in [('trades',engine.trades),('equity',engine.equity)]:
        with (out/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            if rows:
                w = csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    LOG.info('Rapport : %s',out/'report.json')


def simulate(store,c,source,trade_start=None):
    bars = store.bars(source,(*c.symbols,c.index_symbol))
    if not bars: raise ValueError('Aucune donnée. Lancer demo, collect ou import-csv.')
    if not any(b.symbol == c.index_symbol for b in bars):
        raise ValueError('Indice absent : filtre CAC 40 impossible, simulation refusée')
    calendar = store.calendar()
    missing = [b.time for b in bars if calendar.bounds(b.time) is None]
    if missing: raise ValueError('Calendrier incomplet : importer les séances avant le backtest')
    engine = Engine(c,calendar,trade_start)
    report = engine.run(bars)
    report.update({'version':__version__,'source':source,'dataset_sha256':fingerprint(bars),
                   'bars':len(bars),'first_bar':bars[0].time.isoformat(),
                   'synthetic':source=='synthetic',
                   'symbols_with_data':sorted({b.symbol for b in bars}),
                   'missing_symbols':sorted(set(c.symbols)-{b.symbol for b in bars}),
                   'complete_sessions_per_symbol':{s:len(f.history) for s,f in engine.features.items()},
                   'strategy':'ORB15 + approximate VWAP + cumulative RVOL + EMA + CAC',
                   'ttf_scope':'Only fully closed same-day simulated trades; unresolved positions invalidate overnight assumptions'})
    return engine, report, bars


def backtest(args,store,c):
    start = timestamp(args.trade_start) if args.trade_start else None
    engine,report,bars = simulate(store,c,args.source,start)
    run_id = 'backtest-'+uuid.uuid4().hex[:12]
    store.save_run(run_id,'backtest',c,report,{},engine.events)
    write_report(engine,report,args.output or 'data/reports/'+run_id)
    print(json.dumps(report,indent=2,ensure_ascii=False))


def monitor(args,store,c):
    """Delayed event-time paper replay, NOT executable real-time signals.

    Recompute deterministically from frozen input. Refuse historical additions
    before the already-processed watermark, rather than silently rewriting trades.
    """
    lock = Path(args.db+'.monitor.lock')
    try: lock.mkdir()
    except FileExistsError: raise ValueError('Un moniteur ou verrou existe déjà : '+str(lock))
    try:
        tg = None if args.no_telegram else Telegram(c.telegram_chat_id)
        row = store.db.execute('SELECT config,state FROM runs WHERE id=?',(args.run_id,)).fetchone()
        if row:
            if json.loads(row[0]) != json.loads(json.dumps(asdict(c))):
                raise ValueError('Configuration modifiée : choisir un nouveau --run-id')
            state = json.loads(row[1])
        else:
            state = {'trade_start':datetime.now(UTC).isoformat(), 'watermark':None,
                     'fingerprint':None,'event_count':0}
        while True:
            local_now = datetime.now(UTC).astimezone(ZoneInfo('Europe/Paris'))
            # Keep an extra post-close collection window for delayed data.
            # Weekends/nights are skipped. --once remains a diagnostic.
            if not args.once and (local_now.weekday() >= 5 or not 9 <= local_now.hour < 19):
                if tg:
                    try: tg.flush(store)
                    except RuntimeError as exc: LOG.warning('%s',exc)
                time.sleep(c.poll_seconds)
                continue
            stats = collect_yahoo(store,c,days=5)
            if any(v is None for v in stats.values()) or len(stats) != len(c.symbols)+1:
                LOG.warning('Collecte partielle : portefeuille inchangé ce cycle')
            else:
                bars = store.bars('yahoo',(*c.symbols,c.index_symbol))
                if state['watermark']:
                    old = [b for b in bars if b.time <= timestamp(state['watermark'])]
                    if fingerprint(old) != state['fingerprint']:
                        raise ValueError('Historique traité modifié/complété : arrêt pour éviter de réécrire les trades. Nouveau run requis.')
                engine,report,bars = simulate(store,c,'yahoo',timestamp(state['trade_start']))
                if len(engine.events) < state['event_count']:
                    raise ValueError('Événements historiques divergents : arrêt')
                # Stable IDs prevent duplicate queueing on normal restart.
                for i,event in enumerate(engine.events[state['event_count']:],state['event_count']):
                    if event['kind'] in ('BUY','SELL'):
                        text = ('PAPER DIFFÉRÉ — simulation, ne pas exécuter ce signal ancien\n'
                                +event['kind']+' '+event['symbol']+'\nHeure marché UTC : '+event['time']
                                +'\nQuantité virtuelle : '+str(event['qty'])
                                +'\nPrix simulé : '+str(event.get('exit',event.get('entry')))
                                +'\nStop : '+event['stop']+' / Objectif : '+event['target'])
                        if tg: store.enqueue(args.run_id+':'+str(i),text)
                state.update(watermark=bars[-1].time.isoformat(),fingerprint=fingerprint(bars),event_count=len(engine.events))
                store.save_run(args.run_id,'delayed-paper',c,report,state,engine.events)
                write_report(engine,report,'data/reports/'+args.run_id)
                if engine.position and engine.last_time:
                    close = store.calendar().bounds(engine.last_time)[1]
                    if datetime.now(UTC) > close+timedelta(minutes=60):
                        if tg: store.enqueue(args.run_id+':unclosed:'+close.date().isoformat(),
                            'PAPER : liquidation non confirmée faute de données. Résultats incomplets, aucune vente inventée.')
                LOG.info('Capital valorisé %s EUR ; trades clos %s',report['equity'],report['closed_trades'])
            if tg:
                try: tg.flush(store)
                except RuntimeError as exc: LOG.warning('%s',exc)
            if args.once: break
            time.sleep(c.poll_seconds)
    finally:
        lock.rmdir()


def parser():
    p = argparse.ArgumentParser(description='PEA Day Trading Lab — simulation uniquement')
    p.add_argument('--config',default='config.toml')
    p.add_argument('--db',default='data/lab.sqlite3')
    p.add_argument('--env',default='.env')
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('demo',help='Créer des données synthétiques de test')
    sub.add_parser('status',help='État de la base')
    co = sub.add_parser('collect',help='Archiver Yahoo 5m, sans clé API')
    co.add_argument('--days',type=int,default=59)
    im = sub.add_parser('import-csv')
    im.add_argument('file'); im.add_argument('--calendar',required=True)
    im.add_argument('--source',default='local')
    bt = sub.add_parser('backtest')
    bt.add_argument('--source',default='yahoo'); bt.add_argument('--output')
    bt.add_argument('--trade-start',help='ISO UTC, permet de réserver une période antérieure au warm-up')
    sub.add_parser('telegram-test',help='Envoie un message test au chat configuré')
    mo = sub.add_parser('monitor',help='Paper trading différé, interrogation toutes les 5 min')
    mo.add_argument('--run-id',default='paper-1'); mo.add_argument('--once',action='store_true')
    mo.add_argument('--no-telegram',action='store_true')
    return p


def main():
    args = parser().parse_args()
    setup_logging(); load_env(args.env)
    store = None
    try:
        c = Config.load(args.config); store = Store(args.db)
        if args.command=='demo':
            from .demo import seed
            print('Bougies SYNTHÉTIQUES ajoutées :',seed(store))
        elif args.command=='collect':
            print(json.dumps(collect_yahoo(store,c,args.days),indent=2))
        elif args.command=='import-csv':
            bars = load_csv(args.file)
            store.put_sessions(load_calendar_csv(args.calendar))
            print('Bougies ajoutées :',store.put_bars(bars,args.source))
        elif args.command=='backtest': backtest(args,store,c)
        elif args.command=='monitor': monitor(args,store,c)
        elif args.command=='telegram-test':
            Telegram(c.telegram_chat_id).send('PEA Day Trading Lab : connexion réussie. PAPER uniquement.')
            print('Message envoyé.')
        elif args.command=='status':
            for r in store.db.execute('SELECT source,symbol,COUNT(*),MIN(time),MAX(time) FROM bars GROUP BY source,symbol'):
                print(*r,sep=' | ')
    except KeyboardInterrupt:
        LOG.info('Arrêt demandé ; état conservé')
    except Exception as exc:
        # Avoid tracebacks containing request URLs and bot tokens.
        LOG.error('%s: %s',type(exc).__name__,str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Consulter la documentation / vérifier les dépendances et le réseau')
        raise SystemExit(1) from None
    finally:
        if store: store.close()
