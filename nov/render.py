from pathlib import Path
import base64,json,sys,html,zipfile
import argparse
import pandas as pd
ap=argparse.ArgumentParser(description='Render the three-year CTA chart set, snapshot.csv and HTML gallery.')
ap.add_argument('--run-date',default='2026-11-04',help='vintage label used in output filenames (YYYY-MM-DD)')
ap.add_argument('--note',default='4 November 2026 · Sydney. As-of dates vary by source. US vendor quotes dated 3 November are preliminary, not verified final settlements.',help='header note on data dates for the HTML gallery')
args=ap.parse_args()
sys.path[:0]=['src','scripts']
import compare_reported_positions as c
from cta_models.data import load_csv
from cta_models.model import compute_positions
from run_proxy_models import plot
root=Path('nov'); data=Path('dashboard/data'); charts=root/'charts'
charts.mkdir(parents=True,exist_ok=True)
# Use the repo renderer with a market-appropriate source note on each chart.
source=Path(c.__file__).read_text().replace('LME: investment funds and rolling 3M quote. CME markets: CFTC futures-only managed money and unverified Yahoo continuous quote. ', 'LME: investment funds. US metals: managed money. Equities: leveraged funds. US prices: vendor continuous futures. ')
exec(compile(source,str(c.__file__),'exec'),c.__dict__)
results=[]
for m in ['LME_CU','COMEX_HG','LME_AL','LME_NI','LME_ZN','NYMEX_PL','NYMEX_PA','LME_PB','COMEX_GC','COMEX_SI','SGX_IO62','CME_ES','CME_NQ']:
 path=charts/f'{m}_3Y.png'
 if m in ('SGX_IO62','LME_PB'):
  # No reported-positioning series is bundled for these two: model-only chart.
  p=load_csv(data/('sgx_io62_yahoo_research_proxy.csv' if m=='SGX_IO62' else 'lme_lead_3m_westmetall_2008-2026_staged.csv'),m); d=compute_positions(p); plot(m,p,d,path,years=3); d=d.rename(columns={'date':'price_date'}); w=None;name='Iron ore · CME TIO proxy' if m=='SGX_IO62' else 'LME lead · 3M (model only)'
 elif m.startswith('CME_'):
  name={'CME_ES':'E-mini S&P 500','CME_NQ':'E-mini Nasdaq-100'}[m]
  c.MARKETS[m]=(name,'','index points','#4372a2')
  from cta_models.config import MARKETS,Market
  from cta_models.indicators import rsi
  MARKETS[m]=Market(m,'CME',name,'USD','index points',50 if m=='CME_ES' else 20,'USD per point','quarterly')
  d=compute_positions(pd.read_csv(data/f'{m}_vendor.csv'));d['rsi14']=rsi(d.close);d.to_csv(root/f'{m}_daily.csv',index=False);d=d.rename(columns={'date':'price_date'});w=pd.read_csv(root/f'{m}_reported.csv',parse_dates=['position_date'])
  c.chart(m,d,w,path,years=3)
 else:
  name=c.MARKETS[m][0];_,d,w=c.build(m,data);c.chart(m,d,w,path,years=3)
 last=d.iloc[-1];day=last.price_date.date().isoformat()
 results.append(dict(market=m,name=name,date=day,price=last.close,score=100*last.exposure,prior_score=100*d.exposure.iloc[-2],report_date='' if w is None else str(w.iloc[-1].position_date.date()),net_pct_oi=None if w is None else w.iloc[-1].reported_net_pct_oi))
pd.DataFrame(results).to_csv(root/'snapshot.csv',index=False)
gallery=root/f'CTA_3Y_{args.run_date}.html'
out=['<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Three-year CTA positioning</title><style>body{font:16px system-ui;color:#203448;background:#edf2f5;max-width:1220px;margin:auto;padding:22px}section{background:white;padding:16px;margin:22px 0;border-radius:12px}img{width:100%;height:auto}nav a{display:inline-block;margin:4px 10px 4px 0;color:#235885}</style><h1>Three-year CTA positioning</h1><p>'+html.escape(args.note)+' Scores are model exposures on a −100 to +100 scale; reported positions are weekly category net as % of open interest. The two axes have different units.</p><nav>']
for r in results: out.append(f'<a href="#{r["market"]}">{html.escape(r["name"])}</a>')
out.append('</nav>')
for r in results:
 m=r['market'];img=base64.b64encode((charts/f'{m}_3Y.png').read_bytes()).decode()
 out.append(f'<section id="{m}"><h2>{html.escape(r["name"])} · {r["score"]:+.1f}</h2><p>Price date: {r["date"]}. Report position date: {r["report_date"] or "unavailable"}. </p><img src="data:image/png;base64,{img}"></section>')
gallery.write_text(''.join(out))
with zipfile.ZipFile(root/f'CTA_3Y_{args.run_date}.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in [*charts.glob('*.png'),root/'snapshot.csv',root/'equity.py',*root.glob('CME*.csv')]:z.write(f,f.name)
print(pd.DataFrame(results).round(2).to_string(index=False))
