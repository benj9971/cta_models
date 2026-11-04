from pathlib import Path
import sys,datetime as dt
sys.path[:0]=['src','scripts']
from cta_models.config import Market,MARKETS
from cta_models.model import compute_positions
from cta_models.indicators import rsi
import fetch_research_price_proxies as vendor
import pandas as pd, numpy as np, requests
from concurrent.futures import ThreadPoolExecutor
out=Path('nov')
def run(pair):
 symbol,code,name,mult=pair
 m='CME_'+symbol
 MARKETS[m]=Market(m,'CME',name,'USD','index points',mult,'USD per index point','quarterly')
 vendor.MARKETS[m]=(symbol+'=F','index points',1.)
 rows,_=vendor.fetch(m,dt.date(2026,11,3))
 prices=pd.DataFrame(rows); prices.to_csv(Path('dashboard/data')/f'{m}_vendor.csv',index=False)
 daily=compute_positions(prices);daily['rsi14']=rsi(daily.close);daily.to_csv(out/f'{m}_daily.csv',index=False)
 q=requests.get('https://publicreporting.cftc.gov/resource/gpe5-46if.json',params={'$where':f"cftc_contract_market_code='{code}' and report_date_as_yyyy_mm_dd >= '2023-10-01' and report_date_as_yyyy_mm_dd <= '2026-10-27'",'$limit':1000,'$order':'report_date_as_yyyy_mm_dd'},timeout=35);q.raise_for_status()
 d=pd.DataFrame(q.json());print(m,d.market_and_exchange_names.unique(),[k for k in d if 'lev_money' in k][:8],flush=True)
 assert d.cftc_contract_market_code.eq(code).all() and len(d)>150
 d['position_date']=pd.to_datetime(d.report_date_as_yyyy_mm_dd);assert d.position_date.is_unique
 d['reported_net']=d.lev_money_positions_long.astype(int)-d.lev_money_positions_short.astype(int);d['reported_net_pct_oi']=100*d.reported_net/d.open_interest_all.astype(int)
 d['reported_unit']='contracts';d.to_csv(out/f'{m}_reported.csv',index=False);print(m,daily.iloc[-1][['date','close','exposure']].to_dict(),flush=True)
with ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(run,[('ES','13874A','S&P 500',50),('NQ','209742','Nasdaq-100',20)]))
