"""
optimizer_msba_v1_engine.py
===========================
Tax-aware portfolio accounting engine with tax-loss harvesting (MSBA v1).

Public API:
    run_optimizer_simulation(...)  →  dict with nav_series, trades, gains, tax_paid

Adapted from portfolio_accounting_engine_v2.2.ipynb.
All logic is self-contained — no modifications to the Streamlit host required
beyond importing this module and calling the public function.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import warnings

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Schema constants
# ─────────────────────────────────────────────────────────────────────────────

LOT_COLUMNS = [
    "lot_id", "ticker", "open_date", "shares",
    "cost_basis", "total_cost", "source",
]

TRADE_COLUMNS = [
    "trade_id", "trade_date", "ticker", "action",
    "shares", "price", "gross_value",
    "spread_cost", "slippage_cost", "fixed_cost", "variable_cost", "total_cost",
    "net_cash_impact",
]

REALIZED_COLUMNS = [
    "event_id", "event_date", "ticker", "event_type",
    "shares", "proceeds", "cost_basis", "gain_loss",
    "holding_days", "gain_type", "tax_rate", "tax_owed", "lot_id",
]


# ─────────────────────────────────────────────────────────────────────────────
# Trading Costs Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TradingCosts:
    """
    Configurable transaction cost model.

    Attributes
    ----------
    fixed_cost_per_trade : float
        Flat dollar commission charged per trade (each buy or sell), e.g. 1.00.
    variable_cost_bps : float
        Variable cost as basis points of gross trade value, e.g. 5 = 0.05%.
        Covers exchange fees, clearing, etc.
    slippage_bps : float
        Market-impact slippage as basis points of gross trade value, e.g. 5 = 0.05%.
        Worsens the execution price (buys fill higher, sells fill lower).
    """
    fixed_cost_per_trade: float = 0.0
    variable_cost_bps: float    = 0.0
    slippage_bps: float         = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Tax Engine
# ─────────────────────────────────────────────────────────────────────────────

class TaxEngine:
    """ST/LT capital gains tax with loss carry-forward netting."""

    def __init__(self, st_rate: float, lt_rate: float, lt_holding_days: int = 365):
        self.st_rate = st_rate
        self.lt_rate = lt_rate
        self.lt_days = lt_holding_days
        self.st_loss_cf: float = 0.0
        self.lt_loss_cf: float = 0.0

    def classify(self, open_date, close_date) -> Tuple[str, float]:
        days = (close_date - open_date).days
        if days >= self.lt_days:
            return "LT", self.lt_rate
        return "ST", self.st_rate

    def compute_tax(self, gain: float, gain_type: str) -> float:
        if gain < 0:
            if gain_type == "ST":
                self.st_loss_cf += abs(gain)
            else:
                self.lt_loss_cf += abs(gain)
            return 0.0
        if gain == 0:
            return 0.0

        taxable = gain
        if gain_type == "ST":
            used = min(taxable, self.st_loss_cf)
            taxable -= used; self.st_loss_cf -= used
            used = min(taxable, self.lt_loss_cf)
            taxable -= used; self.lt_loss_cf -= used
            return taxable * self.st_rate
        else:
            used = min(taxable, self.lt_loss_cf)
            taxable -= used; self.lt_loss_cf -= used
            used = min(taxable, self.st_loss_cf)
            taxable -= used; self.st_loss_cf -= used
            return taxable * self.lt_rate


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio
# ─────────────────────────────────────────────────────────────────────────────

class Portfolio:
    """Trade-driven portfolio with lot tracking, realized gain accounting, tax, and trading costs."""

    def __init__(self, initial_cash: float, tax_engine: TaxEngine,
                 trading_costs: TradingCosts = None):
        self.cash = initial_cash
        self.tax = tax_engine
        self.tc = trading_costs or TradingCosts()

        self._lot_ctr = 0
        self._trd_ctr = 0
        self._rel_ctr = 0

        # Lots stored as list-of-dicts for speed (no repeated DataFrame rebuild)
        self._lots: List[dict] = []
        self._lots_idx: Dict[str, List[int]] = {}  # ticker → list of _lots indices
        self._lot_id_map: Dict[str, int] = {}       # lot_id → index

        self._trades: List[dict] = []
        self._realized: List[dict] = []
        self._taxes: List[dict] = []
        self.total_tax_paid: float = 0.0
        self.total_costs_paid: float = 0.0  # cumulative trading costs (spread + slippage + commissions)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _nid(self, prefix: str, counter_attr: str) -> str:
        val = getattr(self, counter_attr) + 1
        setattr(self, counter_attr, val)
        return f"{prefix}{val:06d}"

    def shares_held(self, ticker: str) -> float:
        return sum(
            self._lots[i]["shares"]
            for i in self._lots_idx.get(ticker, [])
            if self._lots[i]["shares"] > 1e-12
        )

    def _open_lots(self, ticker: str) -> List[dict]:
        return [
            self._lots[i]
            for i in self._lots_idx.get(ticker, [])
            if self._lots[i]["shares"] > 1e-12
        ]

    def _sorted_lots_for_sell(self, ticker: str, price: float, date) -> List[dict]:
        """TAX_OPTIMAL ordering: losses first (biggest ST loss first), then smallest gains."""
        lots = self._open_lots(ticker)
        if not lots:
            return lots
        for lot in lots:
            lot["_pnl"] = price - lot["cost_basis"]
            lot["_days"] = (date - lot["open_date"]).days
            lot["_is_loss"] = 1 if lot["_pnl"] < 0 else 0
            lot["_is_lt"] = 1 if lot["_days"] >= self.tax.lt_days else 0
        lots.sort(key=lambda x: (-x["_is_loss"], x["_is_lt"], x["_pnl"]))
        return lots

    # ── buy ───────────────────────────────────────────────────────────────────

    def buy(self, date, ticker: str, shares: float, price_ask: float,
            price_bid: float = None, source: str = "BUY"):
        """
        Execute a buy at PRICEASK with slippage and commission applied.

        Parameters
        ----------
        price_ask : execution reference price (PRICEASK or PRICECLOSE fallback)
        price_bid : PRICEBID used to compute spread cost; if None, spread_cost = 0
        """
        tc = self.tc
        # Slippage worsens the buy fill (pay more than ask)
        exec_price = price_ask * (1.0 + tc.slippage_bps / 10_000.0)
        gross = shares * exec_price

        # Cost components
        slippage_cost = shares * price_ask * tc.slippage_bps / 10_000.0
        variable_cost = gross * tc.variable_cost_bps / 10_000.0
        fixed_cost    = tc.fixed_cost_per_trade
        spread_cost   = (price_ask - price_bid) * shares if price_bid is not None else 0.0

        total_deduction = gross + fixed_cost + variable_cost

        if total_deduction > self.cash + 1e-6:
            # Clamp shares so total deduction fits in available cash
            # total_deduction = shares*(exec_price + variable_cost_rate) + fixed
            rate = exec_price + exec_price * tc.variable_cost_bps / 10_000.0
            shares = max(0.0, (self.cash - fixed_cost) / rate)
            if shares < 1e-12:
                return
            gross         = shares * exec_price
            slippage_cost = shares * price_ask * tc.slippage_bps / 10_000.0
            variable_cost = gross * tc.variable_cost_bps / 10_000.0
            spread_cost   = (price_ask - price_bid) * shares if price_bid is not None else 0.0
            total_deduction = gross + fixed_cost + variable_cost

        if shares < 1e-12:
            return

        total_cost = spread_cost + slippage_cost + fixed_cost + variable_cost
        self.cash -= total_deduction
        self.total_costs_paid += total_cost

        lid = self._nid("L", "_lot_ctr")
        lot = {
            "lot_id": lid, "ticker": ticker, "open_date": date,
            "shares": shares, "cost_basis": exec_price,
            "total_cost": gross, "source": source,
        }
        idx = len(self._lots)
        self._lots.append(lot)
        self._lots_idx.setdefault(ticker, []).append(idx)
        self._lot_id_map[lid] = idx

        self._trades.append({
            "trade_id": self._nid("T", "_trd_ctr"), "trade_date": date,
            "ticker": ticker, "action": source, "shares": shares,
            "price": exec_price, "gross_value": gross,
            "spread_cost": spread_cost, "slippage_cost": slippage_cost,
            "fixed_cost": fixed_cost, "variable_cost": variable_cost,
            "total_cost": total_cost,
            "net_cash_impact": -total_deduction,
        })

    # ── sell ──────────────────────────────────────────────────────────────────

    def sell(self, date, ticker: str, shares: float, price_bid: float,
             price_ask: float = None, lot_selection: str = "TAX_OPTIMAL"):
        """
        Execute a sell at PRICEBID with slippage and commission applied.

        Parameters
        ----------
        price_bid : execution reference price (PRICEBID or PRICECLOSE fallback)
        price_ask : PRICEASK used to compute spread cost; if None, spread_cost = 0
        """
        avail = self.shares_held(ticker)
        if shares > avail + 1e-9:
            shares = avail
        if shares < 1e-12:
            return

        tc = self.tc
        # Slippage worsens the sell fill (receive less than bid)
        exec_price = price_bid * (1.0 - tc.slippage_bps / 10_000.0)
        gross = shares * exec_price

        # Cost components
        slippage_cost = shares * price_bid * tc.slippage_bps / 10_000.0
        variable_cost = gross * tc.variable_cost_bps / 10_000.0
        fixed_cost    = tc.fixed_cost_per_trade
        spread_cost   = (price_ask - price_bid) * shares if price_ask is not None else 0.0
        total_cost    = spread_cost + slippage_cost + fixed_cost + variable_cost

        net_proceeds = gross - fixed_cost - variable_cost

        if lot_selection == "TAX_OPTIMAL":
            lots = self._sorted_lots_for_sell(ticker, exec_price, date)
        else:
            lots = sorted(self._open_lots(ticker), key=lambda x: x["open_date"])

        remaining = shares
        # Costs are allocated pro-rata across lots by share count
        per_share_cost = (fixed_cost + variable_cost) / shares if shares > 1e-12 else 0.0

        for lot in lots:
            if remaining < 1e-12:
                break
            sold = min(lot["shares"], remaining)
            gain_type, tax_rate = self.tax.classify(lot["open_date"], date)
            lot_proceeds = sold * exec_price - sold * per_share_cost
            lot_cost = sold * lot["cost_basis"]
            gain = lot_proceeds - lot_cost
            tax = self.tax.compute_tax(gain, gain_type)

            eid = self._nid("R", "_rel_ctr")
            self._realized.append({
                "event_id": eid, "event_date": date, "ticker": ticker,
                "event_type": "SALE", "shares": sold, "proceeds": lot_proceeds,
                "cost_basis": lot_cost, "gain_loss": gain,
                "holding_days": (date - lot["open_date"]).days,
                "gain_type": gain_type, "tax_rate": tax_rate,
                "tax_owed": tax, "lot_id": lot["lot_id"],
            })
            if tax > 0:
                self.cash -= tax
                self.total_tax_paid += tax
                self._taxes.append({"date": date, "event_id": eid, "amount": tax})

            lot["shares"] -= sold
            lot["total_cost"] = lot["shares"] * lot["cost_basis"]
            remaining -= sold

        self.cash += net_proceeds
        self.total_costs_paid += total_cost

        self._trades.append({
            "trade_id": self._nid("T", "_trd_ctr"), "trade_date": date,
            "ticker": ticker, "action": "SELL", "shares": shares,
            "price": exec_price, "gross_value": gross,
            "spread_cost": spread_cost, "slippage_cost": slippage_cost,
            "fixed_cost": fixed_cost, "variable_cost": variable_cost,
            "total_cost": total_cost,
            "net_cash_impact": net_proceeds,
        })

    # ── dividend ──────────────────────────────────────────────────────────────

    def process_dividend(self, date, ticker: str, div_per_share: float,
                         price_ask: float, reinvest: bool, price_bid: float = None):
        held = self.shares_held(ticker)
        if held < 1e-12:
            return
        gross = held * div_per_share
        # No separate dividend tax in MSBA v1 — dividends treated as income
        self.cash += gross

        if reinvest and price_ask > 0:
            drip_shares = gross / price_ask
            self.buy(date, ticker, drip_shares, price_ask, price_bid=price_bid, source="DRIP")

    # ── valuation ─────────────────────────────────────────────────────────────

    def market_value(self, prices: Dict[str, float]) -> float:
        mv = 0.0
        for lot in self._lots:
            if lot["shares"] > 1e-12:
                mv += lot["shares"] * prices.get(lot["ticker"], 0.0)
        return mv

    def nav(self, prices: Dict[str, float]) -> float:
        return self.market_value(prices) + self.cash

    # ── output accessors ──────────────────────────────────────────────────────

    def trades_df(self) -> pd.DataFrame:
        if not self._trades:
            return pd.DataFrame(columns=TRADE_COLUMNS)
        return pd.DataFrame(self._trades)

    def realized_df(self) -> pd.DataFrame:
        if not self._realized:
            return pd.DataFrame(columns=REALIZED_COLUMNS)
        return pd.DataFrame(self._realized)


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Driver
# ─────────────────────────────────────────────────────────────────────────────

def _build_rebalance_set(trading_dates, freq: str):
    """Return set of dates on which to rebalance."""
    dates = pd.DatetimeIndex(trading_dates)
    if len(dates) < 2 or freq == "None":
        return set()
    if freq == "Daily":
        return set(dates[1:])
    rebal = set()
    prev_m, prev_y = dates[0].month, dates[0].year
    prev_w = dates[0].isocalendar()[1]
    for dt in dates[1:]:
        if freq == "Weekly":
            w = dt.isocalendar()[1]
            if w != prev_w or dt.year != prev_y:
                rebal.add(dt)
                prev_w = w; prev_y = dt.year
        elif freq == "Monthly":
            if dt.month != prev_m or dt.year != prev_y:
                rebal.add(dt)
                prev_m = dt.month; prev_y = dt.year
        elif freq == "Quarterly":
            if dt.month in {1, 4, 7, 10} and (dt.month != prev_m or dt.year != prev_y):
                rebal.add(dt)
            if dt.month != prev_m or dt.year != prev_y:
                prev_m = dt.month; prev_y = dt.year
    return rebal


def _build_wide(prices_df: pd.DataFrame, tickers: List[str],
                start_dt, end_dt, field: str) -> pd.DataFrame:
    """Pivot a long prices DataFrame to a wide (date × ticker) matrix for one price field."""
    mask = (
        prices_df["TICKERSYMBOL"].isin(tickers)
        & (prices_df["PRICEDATE"] >= start_dt)
        & (prices_df["PRICEDATE"] <= end_dt)
    )
    sub = prices_df.loc[mask, ["TICKERSYMBOL", "PRICEDATE", field]].copy()
    sub = sub.drop_duplicates(subset=["TICKERSYMBOL", "PRICEDATE"])
    wide = sub.pivot(index="PRICEDATE", columns="TICKERSYMBOL", values=field)
    wide = wide.sort_index().ffill().bfill()
    missing = [t for t in tickers if t not in wide.columns]
    if missing:
        raise ValueError(f"Tickers missing from {field} price data: {missing}")
    return wide[tickers]


def run_optimizer_simulation(
    prices_df: pd.DataFrame,
    dividends_df: Optional[pd.DataFrame],
    tickers: List[str],
    weights: List[float],
    start_date,
    end_date,
    rebalance_frequency: str,
    tax_rates: Dict[str, float],
    tlh_threshold: float,
    reinvest_dividends: bool,
    initial_capital: float = 100_000.0,
    price_field: str = "PRICECLOSE",
    bid_field: str = "PRICEBID",
    ask_field: str = "PRICEASK",
    trading_costs: TradingCosts = None,
    drift_threshold: float = 0.0,
    static: bool = False,
) -> dict:
    """
    Run the MSBA v1 tax-aware portfolio simulation.

    Parameters
    ----------
    prices_df          : long-format prices with TICKERSYMBOL, PRICEDATE, and price columns
    dividends_df       : dividend data with TICKERSYMBOL, PAYDATE, DIVAMOUNT (or None)
    tickers            : list of ticker symbols
    weights            : target weights (same order as tickers)
    start_date/end_date: simulation window
    rebalance_frequency: "Daily" | "Weekly" | "Monthly" | "Quarterly" | "None"
    tax_rates          : {"st_rate": float, "lt_rate": float}
    tlh_threshold      : e.g. 0.05 means harvest if lot is down ≥ 5%
    reinvest_dividends : True → DRIP, False → keep as cash
    initial_capital    : dollar amount
    price_field        : fallback price column (used for NAV and when bid/ask unavailable)
    bid_field          : column name for bid prices (sells execute here)
    ask_field          : column name for ask prices (buys execute here)
    trading_costs      : TradingCosts config; defaults to zero costs if None
    drift_threshold    : absolute weight drift that triggers a rebalance (e.g. 0.05 = 5%);
                         fires independently of calendar rebalances. 0 = disabled.
    static             : if True, no rebalancing (buy-and-hold with TLH only)

    Returns
    -------
    dict with keys: nav_series, trades_df, realized_df, tax_paid_total, costs_paid_total,
                    rebalance_count
    """
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)
    tc = trading_costs or TradingCosts()

    # ── Build wide price matrices ──────────────────────────────────────────────
    # Close prices used for NAV mark-to-market (mid-point valuation)
    wide_close = _build_wide(prices_df, tickers, start_dt, end_dt, price_field)

    # Bid/ask for execution — fall back to close if columns not present
    has_bid = bid_field in prices_df.columns
    has_ask = ask_field in prices_df.columns

    if has_bid and has_ask:
        wide_bid = _build_wide(prices_df, tickers, start_dt, end_dt, bid_field)
        wide_ask = _build_wide(prices_df, tickers, start_dt, end_dt, ask_field)
        # Align indices to close (close is the canonical date grid)
        wide_bid = wide_bid.reindex(wide_close.index).ffill().bfill()
        wide_ask = wide_ask.reindex(wide_close.index).ffill().bfill()
    else:
        # No separate bid/ask data — execution at close price, spread_cost = 0
        wide_bid = wide_close
        wide_ask = wide_close

    trading_dates = wide_close.index.tolist()
    if len(trading_dates) < 2:
        raise ValueError("Not enough trading dates for simulation.")

    # ── Pre-index dividends by (ticker, date) ─────────────────────────────────
    div_lookup: Dict[Tuple[str, pd.Timestamp], float] = {}
    if dividends_df is not None and not dividends_df.empty:
        ddf = dividends_df.copy()
        ddf["PAYDATE"] = pd.to_datetime(ddf["PAYDATE"], errors="coerce")
        if "TICKERSYMBOL" in ddf.columns:
            ddf["TICKERSYMBOL"] = ddf["TICKERSYMBOL"].astype(str).str.strip().str.upper()
            ddf = ddf[ddf["TICKERSYMBOL"].isin(tickers)]
            for _, row in ddf.iterrows():
                key = (row["TICKERSYMBOL"], row["PAYDATE"])
                div_lookup[key] = div_lookup.get(key, 0.0) + float(row["DIVAMOUNT"])

    # ── Rebalance schedule ────────────────────────────────────────────────────
    if static:
        rebal_dates = set()
    else:
        rebal_dates = _build_rebalance_set(trading_dates, rebalance_frequency)

    # ── Initialize portfolio ──────────────────────────────────────────────────
    tax_eng = TaxEngine(
        st_rate=tax_rates.get("st_rate", 0.35),
        lt_rate=tax_rates.get("lt_rate", 0.20),
    )
    pf = Portfolio(initial_capital, tax_eng, trading_costs=tc)

    weight_map = dict(zip(tickers, weights))

    # ── Day 0: initial purchases at ask ───────────────────────────────────────
    day0 = trading_dates[0]
    for tk in tickers:
        alloc = initial_capital * weight_map[tk]
        p_ask = wide_ask.loc[day0, tk]
        p_bid = wide_bid.loc[day0, tk]
        shares = alloc / p_ask
        pf.buy(day0, tk, shares, p_ask, price_bid=p_bid)

    # ── Pre-allocate NAV array ────────────────────────────────────────────────
    n_days = len(trading_dates)
    nav_arr = np.empty(n_days, dtype=np.float64)
    rebal_count = 0

    # Record day 0 NAV (mark-to-market at close)
    prices_d0 = {tk: wide_close.loc[day0, tk] for tk in tickers}
    nav_arr[0] = pf.nav(prices_d0)

    # ── Daily loop ────────────────────────────────────────────────────────────
    for i in range(1, n_days):
        dt = trading_dates[i]
        prices_close = {tk: wide_close.loc[dt, tk] for tk in tickers}
        prices_bid   = {tk: wide_bid.loc[dt, tk]   for tk in tickers}
        prices_ask   = {tk: wide_ask.loc[dt, tk]   for tk in tickers}

        # 1. Dividends — DRIP buys at ask
        for tk in tickers:
            div_amt = div_lookup.get((tk, dt))
            if div_amt is not None and div_amt > 0:
                pf.process_dividend(dt, tk, div_amt, prices_ask[tk],
                                    reinvest_dividends, price_bid=prices_bid[tk])

        # 2. Tax-Loss Harvesting — check each lot against bid price (liquidation value)
        if tlh_threshold > 0:
            for tk in tickers:
                lots_to_harvest = []
                for lot in pf._open_lots(tk):
                    if lot["shares"] < 1e-12:
                        continue
                    # Use bid price for unrealized P&L (what we'd actually receive)
                    unrealized_pct = (prices_bid[tk] - lot["cost_basis"]) / lot["cost_basis"]
                    if unrealized_pct <= -tlh_threshold:
                        lots_to_harvest.append((lot["lot_id"], lot["shares"]))

                for lot_id, lot_shares in lots_to_harvest:
                    # Sell at bid, rebuy at ask
                    pf.sell(dt, tk, lot_shares, prices_bid[tk],
                            price_ask=prices_ask[tk], lot_selection="TAX_OPTIMAL")
                    pf.buy(dt, tk, lot_shares, prices_ask[tk],
                           price_bid=prices_bid[tk], source="TLH_REBUY")

        # 3. Rebalancing — sells at bid, buys at ask; NAV based on close
        rebalanced_this_day = False
        if dt in rebal_dates:
            rebalanced_this_day = True
            total_val = pf.nav(prices_close)
            if total_val > 0:
                # Sell overweight positions at bid
                for tk in tickers:
                    current_val = pf.shares_held(tk) * prices_close[tk]
                    target_val = total_val * weight_map[tk]
                    if current_val > target_val + 1.0:
                        sell_shares = (current_val - target_val) / prices_bid[tk]
                        pf.sell(dt, tk, sell_shares, prices_bid[tk],
                                price_ask=prices_ask[tk], lot_selection="TAX_OPTIMAL")

                # Recalculate NAV after sells
                total_val = pf.nav(prices_close)

                # Buy underweight positions at ask
                for tk in tickers:
                    current_val = pf.shares_held(tk) * prices_close[tk]
                    target_val = total_val * weight_map[tk]
                    if target_val > current_val + 1.0:
                        buy_shares = (target_val - current_val) / prices_ask[tk]
                        pf.buy(dt, tk, buy_shares, prices_ask[tk], price_bid=prices_bid[tk])

        # 3b. Drift-threshold rebalance (fires only when no calendar rebalance today)
        if drift_threshold > 0 and not rebalanced_this_day:
            total_val = pf.nav(prices_close)
            if total_val > 0:
                current_w = {
                    tk: (pf.shares_held(tk) * prices_close[tk]) / total_val
                    for tk in tickers
                }
                max_drift = max(abs(current_w[tk] - weight_map[tk]) for tk in tickers)
                if max_drift >= drift_threshold:
                    rebalanced_this_day = True
                    # Sell overweights at bid
                    for tk in tickers:
                        current_val = pf.shares_held(tk) * prices_close[tk]
                        target_val  = total_val * weight_map[tk]
                        if current_val > target_val + 1.0:
                            sell_shares = (current_val - target_val) / prices_bid[tk]
                            pf.sell(dt, tk, sell_shares, prices_bid[tk],
                                    price_ask=prices_ask[tk], lot_selection="TAX_OPTIMAL")
                    # Recalculate NAV after sells
                    total_val = pf.nav(prices_close)
                    # Buy underweights at ask
                    for tk in tickers:
                        current_val = pf.shares_held(tk) * prices_close[tk]
                        target_val  = total_val * weight_map[tk]
                        if target_val > current_val + 1.0:
                            buy_shares = (target_val - current_val) / prices_ask[tk]
                            pf.buy(dt, tk, buy_shares, prices_ask[tk], price_bid=prices_bid[tk])

        if rebalanced_this_day:
            rebal_count += 1

        # 4. Record NAV at close prices
        nav_arr[i] = pf.nav(prices_close)

    # ── Build output ──────────────────────────────────────────────────────────
    nav_series = pd.Series(nav_arr, index=trading_dates, name="NAV")
    nav_series.index.name = "PRICEDATE"

    trades = pf.trades_df()
    return {
        "nav_series":       nav_series,
        "trades_df":        trades,
        "realized_df":      pf.realized_df(),
        "tax_paid_total":   pf.total_tax_paid,
        "costs_paid_total": pf.total_costs_paid,
        "rebalance_count":  rebal_count,
    }