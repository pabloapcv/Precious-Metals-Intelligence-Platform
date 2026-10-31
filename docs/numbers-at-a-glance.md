# One-page number sheet

Use this in a meeting. The longer explanation of every page is in [executive-platform-guide.md](executive-platform-guide.md).

## The three numbers that matter

| If you see | It means | It does not mean |
| --- | --- | --- |
| **94% bullish** | The model puts a 94% chance on gold beating its benchmark over the next 10 trading days | A 94% chance of profit |
| **+1.8% expected alpha** | Estimated price change over that window, minus a fixed 1-point hurdle | Profit after costs, or gold’s own forecast |
| **Effective N of 4.8** | The suggested book is about as spread out as five equal positions | That the book holds only five names |

## Signal words

- **Long** — 60%+ chance of beating gold, and extra return is positive
- **Overweight** — 55%+ chance of beating gold
- **Neutral** — 45% to 55%
- **Underweight** — 45% or below
- **Short** — 40% or below, and extra return is negative

## Quality of the model

**AUC 0.50** = coin flip. **Higher is better.** The average across models is the “Mean AUC” in the top bar. This is a test on past data the model had not yet seen. It is not a live fund record.

## Portfolio math, in one line each

- **Weight** — share of a research book that adds up to 100%. No shorts.
- **Mix** — 60% “spread the risk,” 40% “favor the higher expected return.”
- **10-day expected alpha** — weighted average of each name’s extra-return estimate.
- **Volatility** — how much that mix would have moved over roughly the last six months, scaled to a year.
- **Implied Sharpe** — that extra return stretched to a year, divided by that volatility. Useful for comparing runs. Easy to over-read.
- **Top-3 weight** — how much sits in the three largest names.

## Risk words

**Rising** means a gauge crossed a fixed line. It is not a probability.

- Geopolitical index above 0.5 → the “war probability” tile says rising
- Oil-disruption score above 0.4 → oil disruption says rising
- Stored central-bank buying above 30 tonnes → central-bank tile says rising
- Latest gold-ETF flow estimate negative → ETF flows say declining, otherwise stable

## Two buttons

- **Sync** — reload the last saved briefing. Seconds.
- **Run pipeline** — fetch prices, retrain, and rewrite every number. Several minutes.

## The chart caveat

The historical gold line uses **purged as-of scores**: at each date the model was refit with a horizon embargo so labels that would reach into that date were excluded. It is not today’s live model replayed on old features, and it is not a log of calls that were published at the time.

**Live vs paper:** Signal Book and Strategy sleeve use full-sample live registry models. History charts and paper books use as-of scores only.
