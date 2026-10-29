from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Signal:
    side: Literal["BUY", "SELL"]
    candle_time: datetime


class Strategy(Protocol):
    name: str

    def detect(self, candles: list[Candle]) -> Signal | None:
        """Return a signal from completed candles, or None when there is no new entry."""
