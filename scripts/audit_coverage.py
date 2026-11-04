"""Export input coverage and descriptive proxy diagnostics; no predictive claims."""
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cta_models.data import load_csv
from cta_models.model import compute_positions
from cta_models.charting import weekly_last_session
from compare_reported_positions import MARKETS, build, reported

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir', type=Path, default=Path('dashboard/data'))
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    coverage, accuracy, stability, gaps = [], [], [], []
    inputs = {m: v[1] for m,v in MARKETS.items()}
    inputs['SGX_IO62'] = 'sgx_io62_yahoo_research_proxy.csv'
    for market, filename in inputs.items():
        p = load_csv(args.data_dir / filename, market)
        positions = compute_positions(p)
        positions.to_csv(args.output_dir / f'{market.lower()}_daily_positions.csv', index=False)
        last = p['date'].iloc[-1]
        row = dict(market=market, first_price_date=p['date'].iloc[0], last_price_date=last,
            price_rows=len(p), latest_quote=p['close'].iloc[-1], model_score=positions['exposure'].iloc[-1]*100,
            missing_available_at='available_at' not in p, source=';'.join(p['source'].unique()),
            max_calendar_gap_days=p['date'].diff().dt.days.max())
        for i in p.index[p['date'].diff().dt.days > 7]:
            gaps.append(dict(market=market, prior_date=p.loc[i-1,'date'], next_date=p.loc[i,'date'],
                calendar_days=(p.loc[i,'date']-p.loc[i-1,'date']).days))
        if market in MARKETS:
            _, daily, weekly = build(market, args.data_dir)
            archive = reported(args.data_dir, market)
            row.update(report_date=weekly['position_date'].iloc[-1],
                report_net=weekly['reported_net'].iloc[-1],report_net_pct_oi=weekly['reported_net_pct_oi'].iloc[-1],
                report_rows=len(archive), first_report_date=archive['position_date'].iloc[0],
                comparable_report_rows=len(weekly), unmatched_weeks=int(weekly['model_score'].isna().sum()),
                published_at_utc=weekly['published_at_utc'].iloc[-1])
            for label, cutoff in [('all', None),('3y',last-pd.DateOffset(years=3)),('1y',last-pd.DateOffset(years=1))]:
                pair=weekly.dropna(subset=['model_score','reported_net_pct_oi'])
                if cutoff is not None: pair=pair[pair['position_date']>=cutoff]
                changes=pair[['model_score','reported_net_pct_oi']].diff().dropna()
                accuracy.append(dict(market=market,window=label,matched_weeks=len(pair),
                    level_correlation=pair['model_score'].corr(pair['reported_net_pct_oi']),
                    change_correlation=changes['model_score'].corr(changes['reported_net_pct_oi']),
                    sign_agreement_pct=100*(np.sign(pair['model_score'])==np.sign(pair['reported_net_pct_oi'])).mean(),
                    change_direction_agreement_pct=100*(np.sign(changes['model_score'])==np.sign(changes['reported_net_pct_oi'])).mean()))
        else:
            row.update(report_date='',report_net=np.nan,report_net_pct_oi=np.nan,report_rows=0,first_report_date='',
                       comparable_report_rows=0,unmatched_weeks=0,published_at_utc='')
        coverage.append(row)
        valid=positions.dropna(subset=['exposure'])
        sample=valid[valid['date']>=last-pd.DateOffset(years=3)]
        weekly_sample=weekly_last_session(sample)
        def flips(s):
            a=np.sign(s.to_numpy()); return int((a[1:]!=a[:-1]).sum())
        stability.append(dict(market=market, daily_observations=len(sample),weekly_observations=len(weekly_sample),
            daily_sign_changes=flips(sample['exposure']),weekly_display_sign_changes=flips(weekly_sample['exposure']),
            daily_mean_abs_score_change=sample['exposure'].diff().abs().mean()*100,
            weekly_mean_abs_score_change=weekly_sample['exposure'].diff().abs().mean()*100,
            last_week_observation=weekly_sample['date'].iloc[-1],
            weekly_strategy_validated=False))
    for name, rows in [('coverage',coverage),('proxy_accuracy',accuracy),('weekly_display_diagnostics',stability),('long_price_gaps',gaps)]:
        pd.DataFrame(rows).to_csv(args.output_dir/f'{name}.csv',index=False)
    print(pd.DataFrame(coverage).to_string(index=False))
    print('\n3-year descriptive benchmark diagnostics:\n',pd.DataFrame(accuracy).query("window=='3y'").to_string(index=False))

if __name__=='__main__': main()
