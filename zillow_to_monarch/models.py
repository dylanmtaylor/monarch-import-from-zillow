"""Data models for Zillow valuation extraction and Monarch Money balance history."""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ValuationPoint:
    """A single real estate valuation data point from Zillow."""

    date: date
    value: float
    source: str = "zestimate"

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Valuation cannot be negative: {self.value}")


@dataclass
class PropertyMetadata:
    """Metadata about the real estate property."""

    zpid: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    current_zestimate: Optional[float] = None

    @property
    def display_name(self) -> str:
        """Friendly identifier for logs and messages."""
        if self.address:
            parts = [self.address]
            if self.city and self.state:
                parts.append(f"{self.city}, {self.state}")
            return " - ".join(parts)
        if self.zpid:
            return f"ZPID {self.zpid}"
        return "Real Estate Asset"


@dataclass
class ProcessingResult:
    """Result of processing Zillow valuation history into continuous daily balances."""

    raw_points: List[ValuationPoint]
    daily_balances: List[Tuple[date, float]]
    start_date: date
    end_date: date
    initial_value: float
    latest_value: float
    property_metadata: PropertyMetadata
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    interpolation_method: str = "forward-fill"
    warnings: List[str] = field(default_factory=list)

    @property
    def value_change(self) -> float:
        """Net change in valuation across the generated date range."""
        return round(self.latest_value - self.initial_value, 2)

    @property
    def percent_change(self) -> float:
        """Percentage change in valuation across the generated date range."""
        if self.initial_value == 0:
            return 0.0
        return round(((self.latest_value - self.initial_value) / self.initial_value) * 100, 2)
