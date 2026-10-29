# Strategy engine

Calculates a simple moving-average crossover from completed candle closes and checks Demo risk limits.

Signals are BUY, SELL, or NO SIGNAL. A missing, stale, or invalid series returns NO SIGNAL. The engine does not download prices and does not place orders. A signal is not a promise of profit or accuracy.

The Windows agent drops the forming bar before these functions run. The API imports this package only for calculation.
