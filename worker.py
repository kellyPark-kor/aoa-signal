from __future__ import annotations
import argparse, json, logging, logging.handlers, random, time, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml
import pandas as pd
import websocket

from signal_core import indicators, signal, load_rules, DISCLAIMER
from storage import Store
from binance_client import BinancePublic
from notifier import Notifier

KST=timezone(timedelta(hours=9))

def setup_logging(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger(); logger.setLevel(logging.INFO)
    h=logging.handlers.RotatingFileHandler(path,maxBytes=2_000_000,backupCount=5,encoding='utf-8'); h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s')); logger.addHandler(h)
    sh=logging.StreamHandler(); sh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s')); logger.addHandler(sh)
    return logger

def load_config():
    with open('config.yaml','r',encoding='utf-8') as f: return yaml.safe_load(f)

def fmt(v): return 'N/A' if pd.isna(v) else f'{float(v):.4f}'

def make_message(symbol,row,sig,delayed=False):
    close=row['close_time'].to_pydatetime() if hasattr(row['close_time'],'to_pydatetime') else row['close_time']
    if close.tzinfo is None: close=close.replace(tzinfo=timezone.utc)
    kst=close.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S KST'); utc=close.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    prefix='[지연 알림] ' if delayed else ''
    atr=float(row['atr14'])
    stop='롱 예시: 종가 - ATR×2 = %.4f / 숏 예시: 종가 + ATR×2 = %.4f' % (row['close']-2*atr,row['close']+2*atr)
    checks=(
      f"EMA 추세 ✓  | 거래량≥1.5x {'✓' if row['vol_ratio']>=1.5 else '✗'} | "
      f"MACD 방향 {'✓' if ((sig=='LONG' and row['macd_hist']>0) or (sig=='SHORT' and row['macd_hist']<0)) else '✗'} | "
      f"20봉 {'고점 돌파' if sig=='LONG' else '저점 이탈'} ✓"
    )
    return (f"{prefix}{symbol} · {sig} 조건 충족\n"
            f"봉 종료: {kst} / {utc}\n종가: {row['close']:.4f}\n"
            f"RSI(14): {row['rsi14']:.2f} · 거래량배수: {row['vol_ratio']:.2f}x · MACD Hist: {row['macd_hist']:.4f}\n"
            f"조건: {checks}\nATR 손절 예시(실행 지시 아님): {stop}\n\n{DISCLAIMER}")

class Worker:
    def __init__(self,cfg,dry_run=False):
        self.cfg=cfg; rt=cfg['runtime']; self.interval=cfg.get('interval','1h'); self.symbols=[s.upper() for s in cfg['symbols']]
        self.rest=BinancePublic(cfg['rest_base_urls'],rt.get('rest_timeout_seconds',10)); self.store=Store(rt['sqlite_path']); self.notifier=Notifier(cfg,dry_run=dry_run); self.rules=load_rules(cfg.get('rule_file'))
        self.last_msg={s:time.time() for s in self.symbols}; self.last_ws_connected=0
    def validate_symbols(self):
        live=self.rest.exchange_symbols(); bad=[s for s in self.symbols if s not in live]
        if bad: raise RuntimeError('존재하지 않거나 현재 거래중이 아닌 심볼: '+', '.join(bad))
    def evaluate(self,symbol, delayed=False, initial=False):
        d=self.rest.klines(symbol,self.interval,self.cfg['runtime'].get('history_limit',500))
        # REST latest candle may be incomplete. Always remove it.
        if len(d)<220: raise RuntimeError(f'{symbol}: 지표 계산에 필요한 220봉 미만')
        x=indicators(d)
        closed=x.iloc[:-1].copy()
        last_processed=self.store.last_processed(symbol)
        rows=closed if last_processed is None else closed[closed.open_time.astype('int64')//10**6 > last_processed]
        if initial and last_processed is None:
            # First boot establishes state without sending historical alerts.
            row=closed.iloc[-1]; sig=signal(row,self.rules); ms=int(row.open_time.timestamp()*1000); self.store.mark_processed(symbol,ms,sig,time.time()); self.store.set_state(symbol,sig,ms,time.time()); return
        for _,row in rows.iterrows():
            sig=signal(row,self.rules); prev=self.store.get_state(symbol); prev_sig=prev[0] if prev else 'WAIT'
            kopen=int(row.open_time.timestamp()*1000)
            if prev_sig=='WAIT' and sig in ('LONG','SHORT') and not self.store.was_sent(symbol,kopen,sig):
                msg=make_message(symbol,row,sig,delayed=delayed or (last_processed is not None and kopen < int(d.open_time.iloc[-2].timestamp()*1000)))
                if self._allowed_notification(symbol):
                    res=self.notifier.send(msg)
                    if res.ok: self.store.mark_sent(symbol,kopen,sig,time.time(),delayed)
                    else: logging.error('알림 실패 %s: %s',symbol,res.error)
                else:
                    logging.info('알림 정책에 의해 전송하지 않음: %s %s %s',symbol,kopen,sig)
            self.store.mark_processed(symbol,kopen,sig,time.time()); self.store.set_state(symbol,sig,kopen,time.time())
    def process_kline_event(self,event):
        data=event.get('data',event); k=data.get('k',{})
        if data.get('e')!='kline' or not k.get('x'): return
        symbol=data['s'].upper(); self.evaluate(symbol,delayed=False,initial=False)
    def on_message(self,ws,message):
        now=time.time()
        try:
            event=json.loads(message); data=event.get('data',event); symbol=data.get('s','').upper()
            if data.get('e')=='24hrMiniTicker':
                p=float(data['c']); o=float(data['o']); self.store.upsert_price(symbol,p,(p/o-1)*100,p-o,now)
            elif data.get('e')=='kline': self.last_msg[symbol]=now; self.process_kline_event(event)
        except Exception as e: logging.exception('WebSocket 메시지 처리 오류: %s',e)
    def on_error(self,ws,error): logging.error('WebSocket 오류: %s',error)
    def on_close(self,ws,code,msg): logging.warning('WebSocket 종료 code=%s msg=%s',code,msg)
    def _allowed_notification(self, symbol: str) -> bool:
        n=self.cfg.get('notifications', {})
        now=time.time()
        quiet=n.get('quiet_hours_kst', {}) or {}
        if quiet.get('enabled'):
            now_k=datetime.now(KST).strftime('%H:%M')
            start=quiet.get('start','23:00'); end=quiet.get('end','07:00')
            in_quiet = (start <= now_k < end) if start < end else (now_k >= start or now_k < end)
            if in_quiet:
                logging.info('방해금지 시간이라 알림을 생략합니다: %s', symbol)
                return False
        max_day=int(n.get('max_per_symbol_per_day',10))
        today=datetime.now(KST).strftime('%Y-%m-%d')
        count=self.store.con.execute("SELECT COUNT(*) FROM sent_notifications WHERE symbol=? AND date(datetime(sent_at,'unixepoch','+9 hours'))=?",(symbol,today)).fetchone()[0]
        if count >= max_day:
            logging.warning('일일 알림 상한 도달: %s (%d)',symbol,count)
            return False
        cooldown=float(n.get('cooldown_minutes',0))*60
        if cooldown>0:
            row=self.store.con.execute("SELECT MAX(sent_at) FROM sent_notifications WHERE symbol=?",(symbol,)).fetchone()
            if row and row[0] and now-float(row[0]) < cooldown:
                logging.info('재알림 쿨다운 중: %s',symbol)
                return False
        return True

    def _watchdog(self, stop_event, ws):
        stale=float(self.cfg['runtime'].get('outage_alert_seconds',300))
        reconnect_hours=float(self.cfg['runtime'].get('proactive_reconnect_hours',23))
        started=time.time(); outage=False
        while not stop_event.wait(5):
            now=time.time()
            if now-started >= reconnect_hours*3600:
                logging.info('23시간 선제 재연결을 위해 WebSocket을 종료합니다.')
                try: ws.close()
                except Exception: pass
                return
            last=max(self.last_msg.values()) if self.last_msg else started
            if now-last >= stale and not outage:
                outage=True
                self.notifier.send('AOA Signal 데이터 끊김: %d초 이상 시장 데이터 수신 없음\n%s' % (int(now-last), DISCLAIMER))
            if outage and now-last < stale:
                outage=False
                self.notifier.send('AOA Signal 데이터 수신 복구\n'+DISCLAIMER)

    def run_once(self):
        # Reconnect/restart 백필: 마지막 처리 이후 마감된 봉을 REST로 다시 확인합니다.
        for s in self.symbols:
            try:
                self.evaluate(s, delayed=True, initial=False)
            except Exception:
                logging.exception('재연결 백필 실패 %s', s)
        streams=[]
        for s in self.symbols:
            sl=s.lower(); streams += [f'{sl}@miniTicker',f'{sl}@kline_{self.interval}']
        last=None
        for base in self.cfg['ws_base_urls']:
            url=base.rstrip('/')+'/stream?streams='+'/'.join(streams)
            try:
                logging.info('WebSocket 연결: %s',base)
                ws=websocket.WebSocketApp(url,on_message=self.on_message,on_error=self.on_error,on_close=self.on_close)
                self.last_ws_connected=time.time()
                stop_event=threading.Event()
                watchdog=threading.Thread(target=self._watchdog,args=(stop_event,ws),daemon=True)
                watchdog.start()
                ws.run_forever(ping_interval=0, ping_timeout=None, origin=None)
                stop_event.set()
                return
            except Exception as e: last=e; logging.exception('WebSocket 후보 실패: %s',e)
        raise RuntimeError(f'WebSocket 모든 후보 실패: {last}')
    def run(self):
        self.validate_symbols(); logging.info('AOA Signal worker 시작: %s',','.join(self.symbols)); self.notifier.send('AOA Signal worker 시작\n'+DISCLAIMER)
        for s in self.symbols:
            try: self.evaluate(s,delayed=False,initial=True)
            except Exception: logging.exception('초기 백필 실패 %s',s)
        backoff=2
        while True:
            try:
                self.run_once(); backoff=2
            except KeyboardInterrupt: raise
            except Exception as e:
                logging.exception('worker 오류: %s',e); time.sleep(backoff+random.uniform(0,1)); backoff=min(backoff*2,300)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--test-notify',action='store_true'); args=ap.parse_args()
    cfg=load_config(); setup_logging(cfg['runtime']['log_file'])
    if args.test_notify:
        n=Notifier(cfg,dry_run=args.dry_run); r=n.send('AOA Signal 테스트 알림\n'+DISCLAIMER); print(r); raise SystemExit(0 if r.ok else 1)
    Worker(cfg,dry_run=args.dry_run).run()
