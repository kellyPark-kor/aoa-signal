from __future__ import annotations
import time, logging, requests
import pandas as pd
log=logging.getLogger(__name__)

class BinancePublic:
    def __init__(self, bases, timeout=10):
        self.bases=bases; self.timeout=timeout
    def get(self,path,params=None):
        last=None
        for base in self.bases:
            try:
                r=requests.get(base.rstrip('/')+path,params=params,timeout=self.timeout)
                r.raise_for_status(); return r.json(),base
            except Exception as e:
                last=e; log.warning("REST 실패 %s: %s",base,e)
        raise RuntimeError(f"Binance REST 모든 후보 실패: {last}")
    def exchange_symbols(self):
        data,_=self.get('/api/v3/exchangeInfo'); return {s['symbol'] for s in data.get('symbols',[]) if s.get('status')=='TRADING'}
    def klines(self,symbol,interval='1h',limit=500):
        a,_=self.get('/api/v3/klines',{'symbol':symbol,'interval':interval,'limit':limit})
        cols=['open_time','open','high','low','close','volume','close_time','qav','trades','tbbav','tbqav','ignore']
        d=pd.DataFrame(a,columns=cols)
        for c in ['open','high','low','close','volume']: d[c]=pd.to_numeric(d[c],errors='coerce')
        d['open_time']=pd.to_datetime(d.open_time,unit='ms',utc=True)
        d['close_time']=pd.to_datetime(d.close_time,unit='ms',utc=True)
        return d[['open_time','open','high','low','close','volume','close_time']]
