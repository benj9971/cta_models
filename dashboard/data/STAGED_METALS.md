# Staged LME three-month histories

These CSVs can be loaded as `LME_ZN` and `LME_AL` in the dashboard. The model
uses the same 20/60/120/252-session signals and 10/15/35/40% weights as copper.
On the 8 October 2026 quotes, zinc scores +16.4 and aluminium −46.0 on the
−100 to +100 risk-scaled model scale. These are inferred signal exposures,
not observed CTA holdings.

| File | Rows | First quote | Last quote | Latest quote |
| --- | ---: | --- | --- | ---: |
| `lme_zinc_3m_westmetall_2008-2026_staged.csv` | 4,629 | 2008-06-17 | 2026-10-08 | USD 3,737/t |
| `lme_aluminium_3m_westmetall_2008-2026_staged.csv` | 4,628 | 2008-06-17 | 2026-10-08 | USD 3,069/t |

Sources: Westmetall's yearly [zinc](https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Zn_cash&year=2026)
and [aluminium](https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Al_cash&year=2026)
tables, using only their `LME ... 3-month` price column. The year selector
links back to 2008. Each row is a published daily quote in USD per metric
tonne, not an open/high/low/close bar. The `close` column is the current
import schema's price alias and `signal_close` repeats the same rolling
three-month quote. Neither is a verified executable closing price or a
futures P&L return.

The source has an isolated January–February 2008 price fragment, followed by
no three-month quotes until 17 June 2008. Starting both staged series on
17 June avoids treating that roughly four-month gap as one model observation.
The source also repeats Friday's quote on Saturday 8 November 2008; that row
was removed. Rows with an absent three-month price were omitted, including
aluminium on 13 October 2011. Missing values were not interpolated or filled
with cash prices. Both CSVs have unique, increasing weekday dates, positive
prices, and no gap longer than five calendar days after their start.
