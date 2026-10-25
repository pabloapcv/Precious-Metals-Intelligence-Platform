"""Macro symbols and the listed metals universe."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolDef:
  symbol: str
  yfinance_ticker: str | None
  fred_series: str | None = None
  name: str = ""
  category: str = "macro"


@dataclass(frozen=True)
class Instrument:
  symbol: str
  name: str
  metal: str
  instrument: str
  tier: str
  yfinance_ticker: str | None = None
  priced: bool = True
  scored: bool = True
  note: str = ""


# Rates, FX, energy, and volatility sit beside the metals book. They are context, not metal instruments.
MACRO_CONTEXT: list[SymbolDef] = [
  SymbolDef("DX-Y.NYB", "DX-Y.NYB", "DTWEXBGS", "US Dollar Index", "fx"),
  SymbolDef("US02Y", "^IRX", "DGS2", "2-Year Treasury Yield", "rates"),
  SymbolDef("US10Y", "^TNX", "DGS10", "10-Year Treasury Yield", "rates"),
  SymbolDef("US10Y_REAL", None, "DFII10", "10-Year Real Yield (TIPS)", "rates"),
  SymbolDef("T10YIE", None, "T10YIE", "10-Year Breakeven Inflation", "rates"),
  SymbolDef("NG=F", "NG=F", None, "Natural Gas", "energy"),
  SymbolDef("CL=F", "CL=F", None, "WTI Crude Oil", "energy"),
  SymbolDef("VIX", "^VIX", "VIXCLS", "VIX", "volatility"),
  SymbolDef("SPX", "^GSPC", None, "S&P 500", "equity"),
]

# Priced metals instruments. `scored` means the next pipeline trains a gold-relative model.
METALS_PRICED: list[Instrument] = [
  # Futures
  Instrument("GC=F", "Gold Futures", "gold", "future", "gold", "GC=F"),
  Instrument("MGC=F", "Micro Gold Futures", "gold", "future", "gold", "MGC=F"),
  Instrument("SI=F", "Silver Futures", "silver", "future", "silver", "SI=F"),
  Instrument("SIL=F", "Micro Silver Futures", "silver", "future", "silver", "SIL=F"),
  Instrument("PL=F", "Platinum Futures", "platinum", "future", "pgm", "PL=F"),
  Instrument("PA=F", "Palladium Futures", "palladium", "future", "pgm", "PA=F"),
  Instrument("HG=F", "Copper Futures", "copper", "future", "copper", "HG=F"),
  Instrument("ALI=F", "Aluminum Futures", "aluminum", "future", "base", "ALI=F"),
  # Physically backed ETFs
  Instrument("GLD", "SPDR Gold Shares", "gold", "bullion_etf", "gold", "GLD"),
  Instrument("IAU", "iShares Gold Trust", "gold", "bullion_etf", "gold", "IAU"),
  Instrument("SGOL", "abrdn Physical Gold", "gold", "bullion_etf", "gold", "SGOL"),
  Instrument("GLDM", "SPDR Gold MiniShares", "gold", "bullion_etf", "gold", "GLDM"),
  Instrument("BAR", "GraniteShares Gold Trust", "gold", "bullion_etf", "gold", "BAR"),
  Instrument("OUNZ", "VanEck Merk Gold Trust", "gold", "bullion_etf", "gold", "OUNZ"),
  Instrument("SLV", "iShares Silver Trust", "silver", "bullion_etf", "silver", "SLV"),
  Instrument("SIVR", "abrdn Physical Silver", "silver", "bullion_etf", "silver", "SIVR"),
  Instrument("PPLT", "abrdn Physical Platinum", "platinum", "bullion_etf", "pgm", "PPLT"),
  Instrument("PALL", "abrdn Physical Palladium", "palladium", "bullion_etf", "pgm", "PALL"),
  Instrument("GLTR", "abrdn Physical Precious Metals Basket", "basket", "bullion_etf", "gold", "GLTR"),
  Instrument("CPER", "United States Copper Index", "copper", "bullion_etf", "copper", "CPER"),
  # Miner and royalty ETFs
  Instrument("GDX", "VanEck Gold Miners", "gold", "miner_etf", "senior", "GDX"),
  Instrument("GDXJ", "VanEck Junior Gold Miners", "gold", "miner_etf", "junior", "GDXJ"),
  Instrument("RING", "iShares MSCI Global Gold Miners", "gold", "miner_etf", "royalty", "RING"),
  Instrument("GOAU", "US Global GO Gold and Precious Metal Miners", "gold", "miner_etf", "senior", "GOAU"),
  Instrument("SGDJ", "Sprott Junior Gold Miners", "gold", "miner_etf", "junior", "SGDJ"),
  Instrument("SIL", "Global X Silver Miners", "silver", "miner_etf", "silver", "SIL"),
  Instrument("SILJ", "Amplify Junior Silver Miners", "silver", "miner_etf", "silver", "SILJ"),
  Instrument("COPX", "Global X Copper Miners", "copper", "miner_etf", "copper", "COPX"),
  # Geared products. Priced, not modeled: each is a levered version of a miner or bullion ETF.
  Instrument("NUGT", "Direxion Daily Gold Miners Bull 2x", "gold", "leveraged", "leveraged", "NUGT", scored=False, note="Geared GDX. Not modeled on its own."),
  Instrument("DUST", "Direxion Daily Gold Miners Bear 2x", "gold", "leveraged", "leveraged", "DUST", scored=False, note="Inverse geared GDX. Not modeled on its own."),
  Instrument("JNUG", "Direxion Daily Junior Gold Miners Bull 2x", "gold", "leveraged", "leveraged", "JNUG", scored=False, note="Geared GDXJ. Not modeled on its own."),
  Instrument("JDST", "Direxion Daily Junior Gold Miners Bear 2x", "gold", "leveraged", "leveraged", "JDST", scored=False, note="Inverse geared GDXJ. Not modeled on its own."),
  Instrument("AGQ", "ProShares Ultra Silver", "silver", "leveraged", "leveraged", "AGQ", scored=False, note="Geared silver. Not modeled on its own."),
  Instrument("ZSL", "ProShares UltraShort Silver", "silver", "leveraged", "leveraged", "ZSL", scored=False, note="Inverse geared silver. Not modeled on its own."),
  # Gold producers
  Instrument("NEM", "Newmont", "gold", "producer", "senior", "NEM"),
  Instrument("AEM", "Agnico Eagle Mines", "gold", "producer", "senior", "AEM"),
  Instrument("B", "Barrick Mining", "gold", "producer", "senior", "B"),
  Instrument("KGC", "Kinross Gold", "gold", "producer", "senior", "KGC"),
  Instrument("AU", "AngloGold Ashanti", "gold", "producer", "senior", "AU"),
  Instrument("GFI", "Gold Fields", "gold", "producer", "senior", "GFI"),
  Instrument("HMY", "Harmony Gold", "gold", "producer", "senior", "HMY"),
  Instrument("AGI", "Alamos Gold", "gold", "producer", "mid", "AGI"),
  Instrument("EGO", "Eldorado Gold", "gold", "producer", "mid", "EGO"),
  Instrument("BTG", "B2Gold", "gold", "producer", "mid", "BTG"),
  Instrument("EQX", "Equinox Gold", "gold", "producer", "mid", "EQX"),
  Instrument("IAG", "IAMGOLD", "gold", "producer", "mid", "IAG"),
  Instrument("SSRM", "SSR Mining", "gold", "producer", "mid", "SSRM"),
  Instrument("SA", "Seabridge Gold", "gold", "developer", "junior", "SA"),
  Instrument("NG", "Novagold", "gold", "developer", "junior", "NG"),
  # Silver producers
  Instrument("PAAS", "Pan American Silver", "silver", "producer", "silver", "PAAS"),
  Instrument("HL", "Hecla Mining", "silver", "producer", "silver", "HL"),
  Instrument("CDE", "Coeur Mining", "silver", "producer", "silver", "CDE"),
  Instrument("AG", "First Majestic Silver", "silver", "producer", "silver", "AG"),
  Instrument("FSM", "Fortuna Mining", "silver", "producer", "silver", "FSM"),
  Instrument("EXK", "Endeavour Silver", "silver", "producer", "silver", "EXK"),
  Instrument("MAG", "MAG Silver", "silver", "producer", "silver", "MAG", scored=False, note="No current listing on the price feed."),
  # Royalty and streaming
  Instrument("FNV", "Franco-Nevada", "gold", "royalty", "royalty", "FNV"),
  Instrument("WPM", "Wheaton Precious Metals", "silver", "royalty", "royalty", "WPM"),
  Instrument("RGLD", "Royal Gold", "gold", "royalty", "royalty", "RGLD"),
  Instrument("OR", "OR Royalties", "gold", "royalty", "royalty", "OR"),
  Instrument("TFPM", "Triple Flag Precious Metals", "gold", "royalty", "royalty", "TFPM"),
  Instrument("SAND", "Sandstorm Gold", "gold", "royalty", "royalty", "SAND", scored=False, note="No current listing on the price feed."),
  # Platinum group
  Instrument("SBSW", "Sibanye Stillwater", "pgm", "producer", "pgm", "SBSW"),
  # Copper and diversified metals
  Instrument("FCX", "Freeport-McMoRan", "copper", "producer", "copper", "FCX"),
  Instrument("SCCO", "Southern Copper", "copper", "producer", "copper", "SCCO"),
  Instrument("TECK", "Teck Resources", "copper", "producer", "copper", "TECK"),
  Instrument("HBM", "Hudbay Minerals", "copper", "producer", "copper", "HBM"),
  Instrument("BHP", "BHP Group", "diversified", "producer", "base", "BHP"),
  Instrument("RIO", "Rio Tinto", "diversified", "producer", "base", "RIO"),
  Instrument("VALE", "Vale", "diversified", "producer", "base", "VALE"),
  # Uranium, the other mined metal on the same desks
  Instrument("CCJ", "Cameco", "uranium", "producer", "uranium", "CCJ"),
  Instrument("UEC", "Uranium Energy", "uranium", "producer", "uranium", "UEC"),
  Instrument("URNM", "Sprott Uranium Miners", "uranium", "miner_etf", "uranium", "URNM"),
]

# Instrument classes the industry trades that this price feed cannot mark every day.
METALS_UNPRICED: list[Instrument] = [
  Instrument("LME_ZINC", "LME Zinc", "zinc", "future", "base", priced=False, scored=False, note="No daily series on the free feed."),
  Instrument("LME_NICKEL", "LME Nickel", "nickel", "future", "base", priced=False, scored=False, note="No daily series on the free feed."),
  Instrument("LME_LEAD", "LME Lead", "lead", "future", "base", priced=False, scored=False, note="No daily series on the free feed."),
  Instrument("LME_TIN", "LME Tin", "tin", "future", "base", priced=False, scored=False, note="No daily series on the free feed."),
  Instrument("LME_COBALT", "Cobalt", "cobalt", "future", "base", priced=False, scored=False, note="OTC and assessed prices, not a listed daily close here."),
  Instrument("LEASE", "Gold lease rate / GOFO", "gold", "otc_rate", "gold", priced=False, scored=False, note="Over-the-counter forward rate. Not a listed close."),
  Instrument("SHFE_PREM", "Shanghai gold premium", "gold", "physical", "gold", priced=False, scored=False, note="Location premium versus London. Not in the daily feed."),
  Instrument("COIN_PREM", "Coin and bar premiums", "gold", "physical", "gold", priced=False, scored=False, note="Retail physical premium. Dealer quotes, not an exchange close."),
  Instrument("OPTIONS", "Listed options on futures and ETFs", "basket", "option", "leveraged", priced=False, scored=False, note="Option chains are a separate surface. This book marks underlyings."),
  Instrument("STREAM", "Private streams and offtake", "basket", "private", "royalty", priced=False, scored=False, note="Bilateral contracts. The listed royalty companies are the public version."),
]

METALS_INSTRUMENTS: list[Instrument] = METALS_PRICED + METALS_UNPRICED

MACRO_SYMBOLS: list[SymbolDef] = MACRO_CONTEXT + [
  SymbolDef(item.symbol, item.yfinance_ticker, None, item.name, item.instrument)
  for item in METALS_PRICED
  if item.yfinance_ticker
]

EQUITY_INSTRUMENTS = {"producer", "royalty", "developer"}

MINER_UNIVERSE = {
  "senior": [],
  "mid": [],
  "junior": [],
  "royalty": [],
}

for _item in METALS_PRICED:
  if _item.instrument not in EQUITY_INSTRUMENTS:
    continue
  MINER_UNIVERSE.setdefault(_item.tier, []).append({
    "ticker": _item.symbol,
    "name": _item.name,
    "tier": _item.tier,
  })

ALL_MINERS = [m for tier in MINER_UNIVERSE.values() for m in tier]

PREDICTION_TARGETS = [
  {"entity": item.symbol, "label": item.name, "tier": item.tier}
  for item in METALS_PRICED
  if item.scored
]

# Forecast horizons in trading days.
# 20 ≈ 1 calendar month, 63 ≈ 3 months, 126 ≈ 6 months.
HORIZONS = [5, 10, 20, 63, 126]

HORIZON_LABELS: dict[int, str] = {
  5: "5d",
  10: "10d",
  20: "1m",
  63: "3m",
  126: "6m",
}

HORIZON_DESCRIPTIONS: dict[int, str] = {
  5: "about one week",
  10: "about two weeks",
  20: "about one month",
  63: "about three months",
  126: "about six months",
}


def horizon_label(days: int) -> str:
  return HORIZON_LABELS.get(days, f"{days}d")


# Flow estimates stay on the two share-count series the ETL already knows how to read.
GOLD_ETFS = ["GLD", "IAU"]
