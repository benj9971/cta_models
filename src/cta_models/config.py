from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    exchange: str
    commodity: str
    currency: str
    price_unit: str
    contract_size: float | None
    contract_unit: str
    convention: str

    @property
    def contract_size_tonnes(self) -> float | None:
        """Legacy convenience for base metals; precious metals return None."""
        if self.contract_size is None:
            return None
        if self.contract_unit == "metric tonnes":
            return self.contract_size
        if self.contract_unit == "pounds":
            return self.contract_size * 0.00045359237
        return None


MARKETS = {
    "LME_CU": Market("LME_CU", "LME", "copper", "USD", "USD/t", 25.0, "metric tonnes",
                     "rolling three-month prompt; use a consistent closing quote"),
    "LME_NI": Market("LME_NI", "LME", "nickel", "USD", "USD/t", 6.0, "metric tonnes",
                     "rolling three-month prompt; use a consistent published quote"),
    "LME_ZN": Market("LME_ZN", "LME", "zinc", "USD", "USD/t", 25.0, "metric tonnes",
                     "rolling three-month prompt; use a consistent published quote"),
    "LME_AL": Market("LME_AL", "LME", "aluminium", "USD", "USD/t", 25.0, "metric tonnes",
                     "rolling three-month prompt; use a consistent published quote"),
    "COMEX_HG": Market("COMEX_HG", "COMEX", "copper", "USD", "US cents/lb", 25000.0, "pounds",
                       "monthly futures; signal_close must be roll adjusted"),
    "NYMEX_PL": Market("NYMEX_PL", "NYMEX", "platinum", "USD", "USD/troy oz", 50.0, "troy ounces",
                       "monthly futures; signal_close must be roll adjusted"),
    "COMEX_GC": Market("COMEX_GC", "COMEX", "gold", "USD", "USD/troy oz", 100.0, "troy ounces",
                       "monthly futures; signal_close must be roll adjusted"),
    "COMEX_SI": Market("COMEX_SI", "COMEX", "silver", "USD", "USD/troy oz", 5000.0, "troy ounces",
                       "monthly futures; signal_close must be roll adjusted"),
    "SGX_IO62": Market("SGX_IO62", "SGX", "iron ore 62% Fe CFR China", "USD", "USD/dmt", None, "metric tonnes",
                       "IODEX monthly futures; verify contract size and index history; roll-adjust signal_close"),
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
