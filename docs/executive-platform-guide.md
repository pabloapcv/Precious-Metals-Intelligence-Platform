# Precious Metals Intelligence Platform

## What this platform is

This is a morning briefing for gold and gold-mining stocks. It turns market prices, rates, the dollar, and a small set of risk indicators into three kinds of answers:

1. **What kind of market are we in?**
2. **Which gold-related assets look more likely to beat gold over the next few weeks?**
3. **If we sized a book from those views, how concentrated would it be?**

It is a research aid. It is not a trading system, and it does not place orders.

The numbers refresh only when someone runs the **pipeline**. **Sync** only reloads what was last saved. A full run pulls fresh prices, rebuilds the inputs, retrains the models, and rewrites the signals and the suggested portfolio. That takes several minutes.

---

## How to read a number

Almost every percentage on the screen comes from one of these ideas.

### Chance of beating gold

For each asset (gold itself via GLD, miner ETFs, and individual miners), the platform asks:

> Over the next 5, 10, or 20 trading days, is this asset more likely than not to rise by more than gold?

The answer is a percentage. **50% means no edge.** Above 55% the screen starts calling the view constructive. At 60% or higher, with a positive expected extra return, it labels the view **long**.

That percentage is the output of a statistical model trained on past market conditions: recent price moves, volatility, the dollar, yields, and similar inputs. It is a probability from that model, not a guarantee.

### Expected extra return (“alpha”)

A second model estimates how much the asset’s price might change over that same window. The screen then subtracts a flat **1 percentage point** and calls the remainder expected alpha versus gold.

Example: if the model’s expected price change is 2.8%, the displayed alpha is **1.8%**.

This 1-point subtraction is a simple hurdle built into the software. It is not a live forecast of gold’s own return. Treat alpha as a ranking tool (“this name looks better than that name”), not as a promised profit.

### Chance of beating the senior-miner ETF

The column labeled probability versus GDX is **95% of the chance of beating gold**. It is a shortcut, not a separate forecast. If gold-outperformance is 80%, the GDX figure is shown as 76%.

### Labels on a signal

| Label | Rule, in plain terms |
| --- | --- |
| Long | At least a 60% chance of beating gold, and expected extra return is positive |
| Overweight | At least a 55% chance of beating gold |
| Neutral | Between 45% and 55% |
| Underweight | 45% or lower |
| Short | 40% or lower, and expected extra return is negative |

### Market regime

The platform sorts each day into one of four environments, such as “easing with a weak dollar” or “geopolitical stress.” It does this by looking at how inflation, real yields, the dollar, oil, stocks, gold, and miners have been moving together, then matching today’s pattern to the closest historical pattern.

**Confidence** is how clearly today fits that bucket. A high confidence means the pattern is unambiguous. It does not mean the investment conclusion is certain.

Each environment comes with a standing view: whether gold and miners have historically been helped or hurt in that setting. Those standing views are written into the platform as research hypotheses. They are not recalculated from profits and losses each morning.

### How good the models have been

Before a model is trusted, it is tested on stretches of history it was not trained on. The main score is **AUC**:

- **0.50** means the model was no better than a coin flip at separating winners from losers.
- **Higher is better.** Around 0.70 means it ranked the better outcomes more often than not.
- A blank or missing score means that particular test could not be completed (for example, the test window had only one kind of outcome).

Accuracy is the share of test days the model called correctly using a simple above-or-below 50% cutoff. AUC is the more useful of the two, because a model can be “accurate” by always saying the same thing in a one-sided market.

These tests use shorter windows than a multi-year institutional backtest, because the current database holds roughly two years of daily prices. Read them as a quality check, not as a track record of a live fund.

---

## The bar across the top

This strip is the same on every page. It is a snapshot of the last completed run.

| Item | What it is |
| --- | --- |
| Data bars | How many daily price records are stored |
| Models | How many forecasts exist (9 assets × 3 time windows = 27) |
| Mean AUC | The average quality score across models that have one |
| Regime | Today’s market environment |
| Gold | Gold’s chance of a constructive 10-day outcome, rounded |
| Effective N | How many independent bets the suggested portfolio really is. See Portfolio. |
| Expected alpha | The portfolio’s weighted 10-day extra-return estimate |
| Backend | Which statistical engine produced the models. If LightGBM cannot load, the platform uses a standard alternative and labels it sklearn. |
| Live / Stale | Live means prices and forecasts are both present. Stale means the database is empty and a pipeline run is needed. |

---

## Command Center

The morning page. Everything here uses the **10-day** window unless a label says otherwise.

### Key insights

Short sentences generated from rules, not from a separate forecast:

- Real yields above 2% are described as a headwind for gold. Below 2%, as support versus cash.
- A dollar move of more than 1% over 20 days is described as pressure (if up) or support (if down).
- The current regime name is restated, with a note that miners can move more than gold in that setting.
- If recent central-bank purchases in the stored history add up to more than 30 tonnes, that is called structural demand.
- The miner with the highest expected extra return is named.

### Gold outlook

| Figure | Calculation |
| --- | --- |
| Bullish % | Gold ETF model’s chance of beating the gold benchmark over 10 days, shown as a whole percent |
| Price | Latest stored gold futures price |
| Signal | Bullish if the chance is above 55%, bearish if below 45%, otherwise neutral |
| Expected alpha | Gold model’s expected price change, minus the 1-point hurdle |
| Gauge and bar | The same bullish percentage, drawn visually |

### Market regime

Shows the latest environment name, the confidence as a percent, whether the standing research view for that environment is bullish or bearish for gold and for miners, a one-line description, and the main drivers (for example Fed policy, real rates, the dollar).

### Macro snapshot

These are **descriptions of the latest data**, not model outputs.

| Figure | How the label is chosen |
| --- | --- |
| Real yields | Latest 10-year real yield. If official real-yield data is missing, the platform estimates it as the 10-year Treasury yield minus a measure of expected inflation. |
| 10-year nominal | Latest 10-year Treasury yield |
| Dollar index | Latest level, plus the percent change over the last 20 trading days |
| VIX | Latest equity-volatility reading. Higher means more fear in the stock market. |
| Fed policy | “Hawkish / higher-for-longer” if real yields are above 2%. “Dovish / easing bias” if below 1%. Otherwise “neutral.” This is a label on the yield level, not a forecast of the next Fed meeting. |
| Inflation | “Elevated” if expected inflation is above 2.5%, “cooling” if below 2%, otherwise “moderate.” If that series is missing, the label stays “moderate.” |

### Markets at a glance

Latest prices for gold, silver, oil, copper, the S&P 500, and the senior gold-miner ETF. Gold also shows its 20-day percent change. These are market facts, not forecasts.

---

## Signal Book

The full list of views, one row per asset.

You can switch the window among **5, 10, and 20 trading days**. Search and tier filters (gold, senior, mid, junior, royalty) only change what is shown. They do not change the math.

| Column | Meaning |
| --- | --- |
| Signal | The long / overweight / neutral / underweight / short label from the rules above |
| P(Gold) | Chance of beating gold |
| P(GDX) | 95% of that chance |
| Expected alpha | Expected price change minus 1 point |
| Expected return | The model’s raw expected price change, before the 1-point hurdle |
| Model | Which version produced the row |

**Export CSV** downloads the rows on screen. It does not create a new forecast.

---

## Model Validation

This page answers: “Should we believe the ranking at all?”

| Figure | Meaning |
| --- | --- |
| Models deployed | Count of saved models (asset × time window) |
| Mean walk-forward AUC | Average quality score. Above 0.60 is a reasonable internal bar; 0.50 is a coin flip. |
| Horizons | The 5-, 10-, and 20-day windows |
| Backend | The statistical engine in use |
| Features | How many inputs that model was given |
| Walk-forward AUC and accuracy | That model’s own test scores |
| Folds | How many separate historical test windows were used. More folds means the score is less dependent on one short stretch. |
| Latest P | The current chance of beating gold from that model |
| Status | “Validated” if at least one test window produced a score. Otherwise the test was skipped or could not be scored. |

### What “walk-forward” means here

The model is trained on an earlier block of days, tested on the next block, then the window steps forward and the test is repeated. On the current data set those blocks are shortened automatically so a test is still possible. The goal is to avoid judging the model only on days it has already seen.

The methodology notes on the page describe this process. They are explanations, not live calculations.

---

## Portfolio

A suggested mix, not an account balance. Weights always add up to 100% of the suggested book. Nothing is shorted. The book is limited to the top holdings by weight, then rescaled so they still add to 100%.

### How the weights are chosen

The default method blends two ideas:

- **60%** from spreading risk across assets that do not all move together. Assets that jump around more, or that move in lockstep with the others, get less weight. This is often called hierarchical risk parity. If that library is unavailable, the fallback is simpler: give more weight to the calmer assets.
- **40%** from the models’ expected returns. Higher expected return gets a larger share of this slice.

The blend is then kept only for the largest positions and scaled back to 100%.

### The summary tiles

| Figure | Calculation |
| --- | --- |
| Positions | How many names are in the book |
| Expected alpha (10-day) | Each position’s expected extra return, multiplied by its weight, then added up. A 20% position with 10% alpha contributes 2 points. |
| Annualized volatility | How much the book would have swung in a typical year, using roughly the last six months of daily price moves and today’s weights. This is realized history, not a forecast of future volatility. |
| Implied Sharpe | The 10-day expected alpha, stretched to a full year by multiplying by 25.2 (252 trading days ÷ 10), then divided by that annualized volatility. A higher number means more expected extra return per unit of historical swing. Because the alpha is a model estimate and the 1-point hurdle is rough, this Sharpe can look flattering. Use it to compare runs, not as a fund track record. |
| Effective N | If every name had the same weight, this is how many names that would equal. A book of 8 names that is really one big bet will show an effective N near 1 or 2. Closer to the actual number of names means the book is more evenly spread. It is calculated as 1 divided by the sum of each weight squared. |
| HHI | The concentration score underneath Effective N (the sum of squared weights). Lower means more spread out. |
| Top-3 weight | Share of the book in the three largest positions |

### Allocation chart and tier bars

The donut is the same weights, drawn as slices. Tier exposure adds those weights by category (gold, senior miners, juniors, royalties, and so on). A senior miner ETF and a senior mining company both count as senior.

### Holdings

Each row is rank, ticker, category, portfolio weight, and that name’s own expected alpha. The bar is the weight, not the alpha.

---

## Research Desk

Context for the forecasts. It does not create a new trade.

### Macro chart

Gold, the senior-miner ETF, and VIX over the stored history (up to about a year). These are prices and the volatility index, not model outputs. Gold and miners share the left scale. VIX uses the right scale because it is a different kind of number.

### Regime confidence history

Each day’s confidence that the environment label was the right bucket, drawn as a percent. Hovering or reading the series shows which environment was in force. Confidence near 100% means that day’s pattern clearly matched one bucket.

### Regime definitions

The four environments the platform knows, each with a standing gold view, a standing miner view, and the forces that define it (policy, real rates, the dollar, and so on). These definitions are fixed research notes. The only thing that changes daily is which definition is selected and how confident that selection is.

### Causal hypotheses

A chain of cause-and-effect statements used as the research map. The core chain is:

Fed policy → real interest rates → the dollar → gold → mining margins → mining stocks.

Each link has a direction (does the next step rise or fall?), a plain-language hypothesis, a rough size guide (for example, “a 1% stronger dollar has often lined up with a 0.5% to 1.5% softer gold price”), and an evidence tag of weak, moderate, or strong.

These statements are **not tested automatically each morning**. They explain the worldview the features and regime logic are built around. Evidence tags are judgments stored with the map, not statistics computed from the latest run.

---

## Historical Outlook

How the **chance of beating gold** has moved over time, for gold and for the mining names.

### Gold outlook chart

One line: gold’s bullish percentage on each sampled date. A horizontal line at 50% is the “no edge” line.

| Tile | Calculation |
| --- | --- |
| Latest | The most recent point on the line |
| Period average | Simple average of the points in the window |
| Range | Lowest and highest points |
| Change | Latest minus the first point, in percentage points |
| Data points | How many dates are plotted |

### Signal probability by entity

The same bullish percentage for the names you toggle on. This is how you see whether miners and gold have been agreeing or diverging.

### Regime and macro panels

The same regime-confidence and price history as the Research Desk, limited to the lookback you choose (60, 90, 180, or 252 calendar days) and the forecast window you choose (5, 10, or 20 days).

### Important caveat

The line is **not** a diary of forecasts that were published every day in the past. The platform keeps a true forecast only on days the pipeline is run. To draw a chart, it also **rescores today’s models on older market conditions**, about once every five trading days. So the chart answers: “If we had used the current models back then, what would they have said?” It does not answer: “What did we actually publish on that date?”

Changing the lookback or the forward window and pressing **Apply** redraws the chart from stored scores. It does not retrain the models.

---

## How It Works

An explanation page, not a second set of forecasts. The live figures on it are the same ones used elsewhere, shown next to a plain-language description.

### Example walkthrough

Takes the strongest 10-day signal and spells out the steps: which date’s inputs were used, which model scored them, the chance of beating gold, the chance versus the miner ETF, the expected return and alpha, the label that rule produced, and that model’s test score if one exists.

### The seven-step pipeline

Each step can be opened. “Complete” means that step has rows in the database. The counts (price records, feature values, regime days, models, predictions, portfolio positions) are inventory, not performance.

The seven steps are: load market data, turn prices into model inputs, classify the environment, train and test the models, write today’s signals, build the portfolio, and run the four research summaries below.

### Signal labels, gold explanation, and today’s inputs

Restates the label rules, restates what the gold bullish percentage means, and lists the yield, dollar, dollar trend, VIX, and Fed label currently in use.

### Causal chain

The same cause-and-effect map as the Research Desk, limited to the core links, with the size guide and evidence tag on each link.

### Research agents

Four summaries sit on top of the models. They do not replace them. Each has a confidence that is set by its own rules, and a list of the sentences that fired.

| Agent | What it scores | How |
| --- | --- | --- |
| Macro | A 0–100% macro score for gold | Starts at 50%. Adds when real yields are low (under 1.5%) or the dollar is falling (more than 2% over 20 days). Subtracts when real yields are high (over 2.5%) or the dollar is rising. A small addition if inflation expectations are rising. |
| Geopolitical | Conflict, energy risk, and a gold-support score | Read from the stored geopolitical index, an oil-disruption score, and a conflict-intensity score. Higher readings raise the gold-support score. Sentences appear when the geopolitical index is above 0.5, oil disruption above 0.4, or conflict above 0.5. |
| Mining | A fundamental score per miner, plus an average | Starts at 50% and adjusts for production surprise, cost trend, and whether analyst earnings estimates have been revised up or down. |
| Quant | Signal stability | Set from the average model quality score. It also lists a few inputs treated as important (real-yield trend, dollar, geopolitical index). Those importance weights are currently fixed illustrations, not a fresh ranking computed from the latest model. |

### Features and data sources

Groups the inputs the models actually see:

- Recent returns and momentum
- Volatility and common technical gauges
- Cross-market measures: real yields, the dollar, gold versus oil, VIX
- Miner items: production surprise, cost surprise, earnings-revision momentum, and how tightly the miner has moved with gold

The data-source table states where each series comes from and how often it updates. Prices are market data. Central-bank purchases and parts of the geopolitical series are curated or proxy series, not a full official feed, unless those connections are added later.

---

## Risk Monitor

A traffic-light page. Most items are **rising** or **stable**. They are thresholds, not probabilities of war or of an oil shock.

| Item | Turns “rising” when |
| --- | --- |
| War probability | Geopolitical risk index is above 0.5. Despite the name, this is “the index is elevated,” not a calculated chance of war. |
| Oil disruption | Oil-disruption score is above 0.4 |
| Central-bank buying | Recent stored purchases add up to more than 30 tonnes |
| ETF flows | The latest daily gold-ETF flow proxy is negative. Otherwise “stable.” The screen does not currently mark flows as rising. |

**GPR index** and **conflict intensity** are the underlying 0-to-1 readings behind those labels.

### ETF flows

Dollar figures are estimates of daily and 30-day average flows for the two large gold ETFs, expressed in millions. They are derived from market data as a stand-in for official flow reports. The signal word uses the same ETF rule as the risk list.

### Central-bank buying

Sum of stored monthly purchases, plus the largest buyers in that history and the rising/stable label from the 30-tonne rule. This block depends on the central-bank data loaded into the platform. Treat the tonnes as the dataset’s figure, not as a live World Gold Council release, unless that feed has been connected.

### AI agent scores

The same four agents as on How It Works, shown as bars. A bar at 70% means that agent’s rule-based score is 0.70. It is not a probability that the agent is correct.

---

## What an executive should not assume

- A 90% bullish reading is not a 90% chance of making money. It is the model’s chance that the asset beats the gold benchmark over a short window.
- Expected alpha is not a forecast of profit after costs, and it uses a flat 1-point hurdle rather than a live gold forecast.
- The portfolio is a research allocation. It ignores mandates, liquidity, borrow, position limits, and transaction costs.
- Historical outlook lines are reconstructed with today’s models. They are not an archive of previously published calls.
- Model quality scores are out-of-sample tests on a short history. They are not a live track record.
- Several risk labels are thresholds on proxy indexes. “War probability: rising” means the geopolitical gauge is above its cutoff.
- Nothing on the platform is investment advice or an instruction to trade.
