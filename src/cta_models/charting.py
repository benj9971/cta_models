"""Display sampling for charts; model calculations always use daily observations."""

import pandas as pd


def weekly_last_session(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    """Keep the last observed session in each Saturday–Friday week, including this week."""
    if frame.empty:
        return frame.copy()
    dates = pd.to_datetime(frame[date_column])
    return frame.loc[~dates.dt.to_period("W-FRI").duplicated(keep="last")].copy()
