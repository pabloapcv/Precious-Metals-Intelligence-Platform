# Gold allocation under a purged walk-forward test

## Question

A gold book has two decisions, and they answer different questions.

1. **Gold budget.** Over the next 10 trading days, should the holding be gold futures or the S&P 500?
2. **Gold sleeve.** Given that budget, should the holding be gold miners (GDX) or gold futures?

The live screen also shows a Keep / Add / Reduce stance. That stance mixes a model spread with rules for real yields, the dollar, and a regime label. This note evaluates the model decision directly: hold the asset the model favors, with a cost when it changes its mind. The rule-based stance is documented in the claim inventory and is not the backtest.

## Data

Prices and the feature store come from the local warehouse (`data/pmip.db` unless `DATABASE_URL` is set). Features are the same daily matrix the app trains on: trailing returns, volatility, cross-asset ratios, real yields when the series is present, and dollar trend. The labeled sample is the overlap of that matrix with a complete 10-day forward return for both assets in the pair. On this machine that history is on the order of two years, so every result below is a short-sample result.

Real yields use the FRED series when a key is configured. Without it, the live macro snapshot estimates the real yield. The research models use whatever column is already in the feature store.

## Method

The label on date *t* is 1 when the entity’s return from *t* to *t+10* exceeds the benchmark’s return over the same window. Training rows whose labels reach into the test date are removed. The embargo is 10 trading days, equal to the horizon. Folds step forward by 10 days, so the economic path does not reuse overlapping returns.

Three comparisons sit on the same dates:

- **Always hold** the entity, and always hold the benchmark.
- **Relative momentum.** Hold the entity when its trailing 20-day return exceeds the benchmark’s.
- **Logistic regression** on a small macro set: real yield, dollar trend, gold ratios to equities, oil, and copper, plus trailing return and volatility columns when they exist. Median imputation and scaling are fit on the training fold only.
- **Gradient boosting** (histogram gradient boosting, depth 3, 40 iterations). Each fold keeps the 20 features with the strongest absolute correlation to the label inside that training window.

Discrimination is AUC and accuracy on the purged dates. A constant “always entity” score is reported as AUC 0.5. Calibration bins the boosting probabilities into five buckets and compares the average predicted probability with the realized hit rate.

The wealth curve is the non-overlapping 10-day return of the chosen asset, minus 10 basis points when the position flips. Final wealth, total return, max drawdown, and hit rate are the economic summary. There is no leverage and no short.

Stability refits the logistic model after dropping real-yield and dollar columns and reports how often the binary call agrees.

## What this does not claim

The on-screen “gold bullish %” for GLD is the probability GLD beats gold futures, which is mostly fees and roll. P(beat GDX) on the signal book is 95% of P(beat gold), not a second model. Expected alpha subtracts a flat 1% hurdle from the model’s expected return. Regime gold bias is a fixed label for the hidden-state id. The historical outlook charts apply the current model to past feature rows; they are not this backtest.

The model catalog’s walk-forward AUC uses the same embargo in code from this revision onward. Numbers already stored from an earlier pipeline run were produced before that embargo. `make research` is the table to cite until the pipeline is run again.

## Point-in-time macro data guarantees

Macro observations are stored with point-in-time provenance:

| Field | Meaning |
| --- | --- |
| `release_date` | When the observation was first published and available to trade on. |
| `vintage` | Revision identifier (ALFRED vintage date or "initial" for first release). |
| `lag_assumed` | True when release_date is estimated from a lag rule, not actual ALFRED data. |

**Vintage-exact series:** FRED series with ALFRED history (DGS10, T10YIE, DFII10, etc.) have exact release dates from the ALFRED real-time API. Each revision is tracked separately.

**Lag-assumed series:** Yahoo market data and FRED series without ALFRED history use conservative publication lag rules:
- Daily market data (equities, futures, VIX): T+1 (available next trading day)
- Daily Treasury yields: T+1
- Monthly CPI/inflation: ~45 days after reference month
- Monthly PCE: ~30 days after reference month

Feature construction joins macro data on `release_date <= prediction_date`, ensuring features at date T never use a macro value published after T or a revision released after T. This applies to both live and as-of scoring paths.

The `lag_assumed` flag allows downstream analysis to distinguish exact from estimated release dates.

## Reproduce

```bash
make research
```

That command reloads the feature store, reruns both studies, and rewrites the block below plus `docs/research/results.json` and `docs/research/latest-results.md`. A unit test checks that every training fold ends at least one horizon before its test date.

<!-- RESULTS:START -->

# Latest research results

Generated 2026-10-14T23:05:59+00:00. Horizon 10 trading days. Turnover cost 10 bps when a book flips. Each test date is embargoed by one full horizon, and wealth compounds only on those non-overlapping dates.

## Should the next 10-day holding be gold or the S&P 500?

Sample 537 labeled days, 41 out-of-sample dates, train window 120, positive rate 56.1%.

| Model | AUC | Accuracy | Final wealth | Total return | Max drawdown | Hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gradient boosting | 0.568 | 53.7% | 1.261 | 26.1% | -15.4% | 53.7% |
| Logistic, macro features | 0.529 | 63.4% | 1.594 | 59.4% | -12.9% | 63.4% |
| 20-day relative momentum | 0.556 | 58.5% | 1.682 | 68.2% | -12.9% | 58.5% |
| Always Gold futures | 0.500 | 56.1% | 1.519 | 51.9% | -20.2% | — |
| Always S&P 500 | — | — | 1.269 | 26.9% | -13.7% | — |

Calibration of the gradient-boosted probabilities:

| Predicted bin | Count | Mean predicted | Realized rate |
| --- | ---: | ---: | ---: |
| 0.00–0.20 | 10 | 0.111 | 0.600 |
| 0.20–0.40 | 5 | 0.298 | 0.600 |
| 0.40–0.60 | 7 | 0.485 | 0.429 |
| 0.60–0.80 | 9 | 0.714 | 0.444 |
| 0.80–1.00 | 10 | 0.910 | 0.700 |

Stability: agreement after dropping real yield and the dollar is 100.0% across 41 dates. The full logistic chooses the entity on 68.3% of dates; without yields and the dollar, on 68.3%. Agreement is the share of dates with the same binary call after real-yield and dollar features are removed. Entity rate is how often each version chooses the entity. Agreement near 100% with an entity rate near 0% or 100% means the model almost never switches.

## Inside a gold budget, should the next 10-day holding be miners or gold?

Sample 537 labeled days, 41 out-of-sample dates, train window 120, positive rate 56.1%.

| Model | AUC | Accuracy | Final wealth | Total return | Max drawdown | Hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gradient boosting | 0.389 | 41.5% | 1.615 | 61.5% | -29.2% | 41.5% |
| Logistic, macro features | 0.280 | 43.9% | 1.633 | 63.3% | -31.4% | 43.9% |
| 20-day relative momentum | 0.522 | 46.3% | 1.760 | 76.0% | -25.7% | 46.3% |
| Always Gold miners (GDX) | 0.500 | 56.1% | 2.255 | 125.5% | -29.2% | — |
| Always Gold futures | — | — | 1.519 | 51.9% | -20.2% | — |

Calibration of the gradient-boosted probabilities:

| Predicted bin | Count | Mean predicted | Realized rate |
| --- | ---: | ---: | ---: |
| 0.00–0.20 | 10 | 0.115 | 0.500 |
| 0.20–0.40 | 4 | 0.276 | 1.000 |
| 0.40–0.60 | 9 | 0.530 | 0.667 |
| 0.60–0.80 | 6 | 0.696 | 0.500 |
| 0.80–1.00 | 12 | 0.942 | 0.417 |

Stability: agreement after dropping real yield and the dollar is 100.0% across 41 dates. The full logistic chooses the entity on 68.3% of dates; without yields and the dollar, on 68.3%. Agreement is the share of dates with the same binary call after real-yield and dollar features are removed. Entity rate is how often each version chooses the entity. Agreement near 100% with an entity rate near 0% or 100% means the model almost never switches.

## What each on-screen number is allowed to mean

| Output | Method | Allowed meaning |
| --- | --- | --- |
| P(beat gold futures) | Walk-forward classifier on the feature store | Chance the named asset's forward return exceeds gold futures. For GLD this is a tracking spread, not the chance the gold price rises. |
| P(beat GDX) | 95% of P(beat gold futures). No separate model is trained. | A scaled copy of the gold-relative score. It is not a probability of beating the miners ETF. |
| Expected alpha | Model expected return minus a flat 1% hurdle | A ranking aid. It is not measured excess return versus gold. |
| Keep / Add / Reduce | Rules on the 10-day gold-versus-equity spread, real yield, dollar trend, and the regime table | A current stance for the gold budget. The research backtest is the evidence for whether a model rule would have helped. |
| Regime gold bias | Fixed hypothesis for the fitted HMM state | A label for the environment. It is not a forecast and it is not estimated from this sample's returns. |
| Research AUC and wealth curves | Purged walk-forward, embargo equal to the horizon, 10 bps per flip, non-overlapping 10-day periods | The result to cite. The on-screen model catalog is the operational screen and uses the same embargo only after the next pipeline run. |

<!-- RESULTS:END -->

## Finding on this sample

The run embedded above is the one to cite until `make research` is run again. On 41 non-overlapping out-of-sample dates:

**Gold versus the S&P 500.** Gradient boosting discriminates only slightly (AUC about 0.57) and its probabilities are not calibrated: days scored below 20% still saw gold win about 60% of the time. After a 10 bp flip cost, boosting’s wealth finished near always holding the S&P 500, and behind always holding gold. The 20-day momentum rule and the small logistic model both finished ahead of buy-and-hold gold on this path. That is a short path, not a license to trade the switch. It does say the boosted model is the wrong instrument for the gold-budget decision.

**Miners versus gold.** Boosting AUC is about 0.39, worse than a coin toss, and the highest probability bin won least often. Always holding GDX finished far ahead of every switching rule, because miners rose sharply over the window. A model that steps aside from that trend gives up the return. The sleeve decision on this sample is “the timing model does not earn its switches.”

**Stability.** On both studies the logistic chooses the entity on 68% of dates, and dropping real yield and the dollar does not change a single call. Those two features are not what moves the small model on this sample. Agreement near 100% would be uninformative if the entity rate were near 0% or 100%; here the rate is in between, so the features truly do not flip the decision.

The portfolio use of the project follows that evidence. Gold vs Markets and the signal book are a decision desk with an explicit claim inventory. The number a reviewer should remember is the purged table, not the operational AUC stored from an earlier, overlapping walk-forward.
