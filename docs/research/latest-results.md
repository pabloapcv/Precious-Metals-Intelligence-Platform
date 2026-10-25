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
