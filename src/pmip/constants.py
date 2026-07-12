"""Macro and commodity symbol definitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolDef:
  symbol: str
  yfinance_ticker: str
  fred_series: str | None = None
  name: str = ""
  category: str = "macro"


MACRO_SYMBOLS: list[SymbolDef] = [
  SymbolDef("GC=F", "GC=F", None, "Gold Futures", "commodity"),
  SymbolDef("SI=F", "SI=F", None, "Silver Futures", "commodity"),
  SymbolDef("HG=F", "HG=F", None, "Copper Futures", "commodity"),
  SymbolDef("DX-Y.NYB", "DX-Y.NYB", "DTWEXBGS", "US Dollar Index", "fx"),
  SymbolDef("US02Y", "^IRX", "DGS2", "2-Year Treasury Yield", "rates"),
  SymbolDef("US10Y", "^TNX", "DGS10", "10-Year Treasury Yield", "rates"),
  SymbolDef("US10Y_REAL", None, "DFII10", "10-Year Real Yield (TIPS)", "rates"),
  SymbolDef("T10YIE", None, "T10YIE", "10-Year Breakeven Inflation", "rates"),
  SymbolDef("CL=F", "CL=F", None, "WTI Crude Oil", "commodity"),
  SymbolDef("NG=F", "NG=F", None, "Natural Gas", "commodity"),
  SymbolDef("VIX", "^VIX", "VIXCLS", "VIX", "volatility"),
  SymbolDef("SPX", "^GSPC", None, "S&P 500", "equity"),
  SymbolDef("GDX", "GDX", None, "VanEck Gold Miners ETF", "mining"),
  SymbolDef("GDXJ", "GDXJ", None, "VanEck Junior Gold Miners ETF", "mining"),
  SymbolDef("GLD", "GLD", None, "SPDR Gold Shares", "etf"),
  SymbolDef("IAU", "IAU", None, "iShares Gold Trust", "etf"),
  SymbolDef("RING", "RING", None, "Gold Royalty ETF", "royalty"),
  # Individual miners (for stock-level predictions)
  SymbolDef("NEM", "NEM", None, "Newmont Corporation", "mining"),
  SymbolDef("AEM", "AEM", None, "Agnico Eagle Mines", "mining"),
  SymbolDef("B", "B", None, "Barrick Mining Corporation", "mining"),
  SymbolDef("KGC", "KGC", None, "Kinross Gold", "mining"),
  SymbolDef("AGI", "AGI", None, "Alamos Gold", "mining"),
]

GOLD_ETFS = ["GLD", "IAU"]

MINER_UNIVERSE = {
  "senior": [
    {"ticker": "NEM", "name": "Newmont Corporation", "tier": "senior"},
    {"ticker": "AEM", "name": "Agnico Eagle Mines", "tier": "senior"},
    {"ticker": "B", "name": "Barrick Mining Corporation", "tier": "senior"},
    {"ticker": "KGC", "name": "Kinross Gold", "tier": "senior"},
  ],
  "mid": [
    {"ticker": "AGI", "name": "Alamos Gold", "tier": "mid"},
  ],
  "junior": [],
  "royalty": [],
}

ALL_MINERS = [m for tier in MINER_UNIVERSE.values() for m in tier]

PREDICTION_TARGETS = [
  {"entity": "GLD", "label": "Gold", "tier": "gold"},
  {"entity": "GDX", "label": "Senior Gold Miners", "tier": "senior"},
  {"entity": "GDXJ", "label": "Junior Miners", "tier": "junior"},
  {"entity": "RING", "label": "Gold Royalty Companies", "tier": "royalty"},
] + [{"entity": m["ticker"], "label": m["name"], "tier": m["tier"]} for m in ALL_MINERS]

HORIZONS = [5, 10, 20]
