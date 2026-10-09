from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    exchange: str
    commodity: str
    currency: str
    price_unit: str
    contract_size_tonnes: float
    convention: str


MARKETS = {
    "LME_CU": Market("LME_CU", "LME", "copper", "USD", "USD/t", 25.0,
                     "rolling three-month prompt; use a consistent closing quote"),
    "COMEX_HG": Market("COMEX_HG", "COMEX", "copper", "USD", "US cents/lb", 11.33980925,
                       "monthly futures; signal_close must be roll adjusted"),
}


@dataclass(frozen=True)
class ModelConfig:
    # Trading days. Short models are visible but medium/long dominate the headline.
    horizons: tuple[int, ...] = (20, 60, 120, 252)
    weights: tuple[float, ...] = (0.10, 0.15, 0.35, 0.40)
    volatility_lookback: int = 60
    volatility_target: float = 0.15
    volatility_floor: float = 0.05
    annualization: int = 252

    def __post_init__(self) -> None:
        if not self.horizons or len(self.horizons) != len(self.weights):
            raise ValueError("horizons and weights must have the same nonzero length")
        if any(h < 2 for h in self.horizons) or any(w < 0 for w in self.weights):
            raise ValueError("horizons must be >=2 and weights nonnegative")
        if abs(sum(self.weights) - 1.0) > 1e-9:
            raise ValueError("weights must sum to one")
        if self.volatility_lookback < 2 or self.volatility_target <= 0 or self.volatility_floor <= 0:
            raise ValueError("invalid volatility settings")
