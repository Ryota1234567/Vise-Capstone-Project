"""
06 — Strategy Backtest
======================
Compare portfolio rebalancing strategies side-by-side:
  - Buy & Hold
  - Calendar rebalancing (Daily / Weekly / Monthly / Quarterly)
  - Drift-threshold rebalancing (any % threshold)
  - Combined calendar + threshold

Shows: Portfolio NAV, Total Return, CAGR, Volatility, Sharpe Ratio,
       Max Drawdown, Transaction Costs, Tax Paid, Rebalance Count.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date

from optimizer_msba_v1_engine import run_optimizer_simulation, TradingCosts
from portfolio_shared import load_data, compute_strategy_metrics

st.set_page_config(
    page_title="Strategy Backtest",
    page_icon="📊",
    layout="wide",
)

# ── Persist results across Streamlit re-runs ──────────────────────────────────
if "backtest_results" not in st.session_state:
    st.session_state["backtest_results"] = None

# ── Colour palette for strategy lines ─────────────────────────────────────────
_PALETTE = [
    "#4285F4", "#EA4335", "#FBBC04", "#34A853",
    "#FF6D00", "#46BDC6", "#AB47BC", "#EC407A",
    "#26A69A", "#D4E157", "#78909C", "#FF7043",
]


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

st.sidebar.title("Strategy Backtest")

# ── Portfolio inputs ───────────────────────────────────────────────────────────
st.sidebar.markdown("### Portfolio")
tickers_raw = st.sidebar.text_input(
    "Tickers (comma-separated)", value="SPY, QQQ, TLT",
    help="E.g. SPY, QQQ, TLT"
)
weights_raw = st.sidebar.text_input(
    "Weights % (comma-separated, must sum to 100)", value="50, 30, 20",
    help="E.g. 50, 30, 20"
)

# ── Date range ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Date Range")
col_s, col_e = st.sidebar.columns(2)
start_date = col_s.date_input("Start", value=date(2019, 1, 1))
end_date   = col_e.date_input("End",   value=date(2024, 1, 1))

initial_capital = st.sidebar.number_input(
    "Initial Capital ($)", min_value=1_000, max_value=100_000_000,
    value=100_000, step=10_000, format="%d",
)

# ── Tax rates ──────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Tax Rates")
st_rate = st.sidebar.number_input(
    "Short-Term Rate (%)", min_value=0.0, max_value=60.0,
    value=35.0, step=1.0, format="%.1f",
) / 100.0
lt_rate = st.sidebar.number_input(
    "Long-Term Rate (%)", min_value=0.0, max_value=40.0,
    value=20.0, step=1.0, format="%.1f",
) / 100.0
tax_rates = {"st_rate": st_rate, "lt_rate": lt_rate}

# ── Trading cost assumptions ───────────────────────────────────────────────────
st.sidebar.markdown("### Trading Cost Assumptions")
st.sidebar.caption(
    "Defaults reflect commission-free brokers with typical market-impact slippage."
)
fixed_cost = st.sidebar.number_input(
    "Fixed Cost per Trade ($)", min_value=0.0, max_value=50.0,
    value=0.0, step=0.50, format="%.2f",
    help="Flat commission per order (each buy or sell)",
)
variable_bps = st.sidebar.number_input(
    "Variable Cost (bps)", min_value=0.0, max_value=50.0,
    value=2.0, step=0.5, format="%.1f",
    help="Exchange/SEC fees as basis points of trade value (2 bps = 0.02%)",
)
slippage_bps = st.sidebar.number_input(
    "Slippage (bps)", min_value=0.0, max_value=100.0,
    value=5.0, step=0.5, format="%.1f",
    help="Market-impact slippage as basis points of trade value (5 bps = 0.05%)",
)
trading_costs = TradingCosts(
    fixed_cost_per_trade=fixed_cost,
    variable_cost_bps=variable_bps,
    slippage_bps=slippage_bps,
)

# ── TLH toggle ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Tax-Loss Harvesting")
tlh_threshold = st.sidebar.number_input(
    "TLH Loss Threshold (%)", min_value=0.0, max_value=50.0,
    value=0.0, step=0.5, format="%.1f",
    help="Harvest lots down ≥ this % from cost basis. 0 = disabled.",
) / 100.0

# ── Strategy selection ─────────────────────────────────────────────────────────
st.sidebar.markdown("### Strategies to Compare")

cal_options = ["Buy & Hold", "Daily", "Weekly", "Monthly", "Quarterly"]
selected_cal = st.sidebar.multiselect(
    "Calendar Strategies",
    options=cal_options,
    default=["Buy & Hold", "Monthly", "Quarterly"],
)

threshold_raw = st.sidebar.text_input(
    "Threshold-Only Values (%)", value="5, 10, 20",
    help="Comma-separated drift thresholds. Leave blank to skip.",
)

combined_options = [
    "Monthly + 5%", "Monthly + 10%", "Monthly + 20%",
    "Quarterly + 5%", "Quarterly + 10%",
]
selected_combined = st.sidebar.multiselect(
    "Combined Strategies (Calendar + Threshold)",
    options=combined_options,
    default=["Monthly + 10%"],
)

run_btn = st.sidebar.button("▶  Run Backtest", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Parse inputs & validate
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tickers(raw: str):
    return [t.strip().upper() for t in raw.split(",") if t.strip()]

def _parse_weights(raw: str):
    try:
        return [float(w.strip()) for w in raw.split(",") if w.strip()]
    except ValueError:
        return []

def _parse_thresholds(raw: str):
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                out.append(float(part))
            except ValueError:
                pass
    return out

def _build_strategy_list(selected_cal, threshold_values, selected_combined):
    """Convert UI selections to a list of strategy config dicts."""
    freq_map = {
        "Buy & Hold": "None",
        "Daily": "Daily",
        "Weekly": "Weekly",
        "Monthly": "Monthly",
        "Quarterly": "Quarterly",
    }
    combined_map = {
        "Monthly + 5%":   ("Monthly",   0.05),
        "Monthly + 10%":  ("Monthly",   0.10),
        "Monthly + 20%":  ("Monthly",   0.20),
        "Quarterly + 5%": ("Quarterly", 0.05),
        "Quarterly + 10%":("Quarterly", 0.10),
    }
    strategies = []
    for label in selected_cal:
        strategies.append({
            "label": label,
            "freq": freq_map[label],
            "drift": 0.0,
        })
    for pct in threshold_values:
        strategies.append({
            "label": f"Threshold {pct:g}%",
            "freq": "None",
            "drift": pct / 100.0,
        })
    for label in selected_combined:
        freq, drift = combined_map[label]
        strategies.append({
            "label": label,
            "freq": freq,
            "drift": drift,
        })
    return strategies


# ─────────────────────────────────────────────────────────────────────────────
# Main body
# ─────────────────────────────────────────────────────────────────────────────

st.title("Strategy Backtest")
st.caption(
    "Run the tax-aware optimizer engine across multiple rebalancing strategies "
    "and compare risk, return, and transaction costs side-by-side."
)

# ── Run simulations only when button is explicitly clicked ─────────────────────
if run_btn:
    tickers = _parse_tickers(tickers_raw)
    weights_pct = _parse_weights(weights_raw)
    threshold_values = _parse_thresholds(threshold_raw)

    errors = []
    if not tickers:
        errors.append("Enter at least one ticker.")
    if not weights_pct:
        errors.append("Enter weights (numbers, comma-separated).")
    elif len(weights_pct) != len(tickers):
        errors.append(f"Number of weights ({len(weights_pct)}) must match tickers ({len(tickers)}).")
    else:
        wsum = sum(weights_pct)
        if abs(wsum - 100.0) > 0.5:
            errors.append(f"Weights sum to {wsum:.1f}% — must be 100%.")
    if end_date <= start_date:
        errors.append("End date must be after start date.")
    if not (selected_cal or threshold_values or selected_combined):
        errors.append("Select at least one strategy.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    weights = [w / 100.0 for w in weights_pct]
    weights = [w / sum(weights) for w in weights]

    strategies = _build_strategy_list(selected_cal, threshold_values, selected_combined)
    if not strategies:
        st.error("No strategies to run. Select at least one.")
        st.stop()

    with st.spinner("Loading price data..."):
        try:
            df = load_data()
        except Exception as e:
            st.error(f"Failed to load price data: {e}")
            st.stop()

    available = set(df["TICKERSYMBOL"].unique())
    missing_tickers = [t for t in tickers if t not in available]
    if missing_tickers:
        st.error(f"Tickers not found in dataset: {', '.join(missing_tickers)}")
        st.stop()

    new_results = {}
    progress = st.progress(0.0, text="Running strategies...")
    for idx, strat in enumerate(strategies):
        progress.progress(
            idx / len(strategies),
            text=f"Running: {strat['label']}  ({idx + 1}/{len(strategies)})",
        )
        try:
            sim = run_optimizer_simulation(
                prices_df=df,
                dividends_df=None,
                tickers=tickers,
                weights=weights,
                start_date=str(start_date),
                end_date=str(end_date),
                rebalance_frequency=strat["freq"],
                drift_threshold=strat["drift"],
                tax_rates=tax_rates,
                tlh_threshold=tlh_threshold,
                reinvest_dividends=False,
                initial_capital=float(initial_capital),
                price_field="PRICECLOSE",
                bid_field="PRICEBID",
                ask_field="PRICEASK",
                trading_costs=trading_costs,
                static=(strat["freq"] == "None" and strat["drift"] == 0.0),
            )
            nav = sim["nav_series"]
            m = compute_strategy_metrics(nav.values, float(initial_capital))
            new_results[strat["label"]] = {
                "nav": nav,
                "trades_df": sim["trades_df"],
                "realized_df": sim["realized_df"],
                "tax_paid": sim["tax_paid_total"],
                "costs_paid": sim["costs_paid_total"],
                "rebalance_count": sim["rebalance_count"],
                **m,
            }
        except Exception as e:
            st.warning(f"Strategy '{strat['label']}' failed: {e}")

    progress.progress(1.0, text="Done.")
    progress.empty()

    if not new_results:
        st.error("All strategies failed. Check tickers and date range.")
        st.stop()

    st.session_state["backtest_results"] = new_results

# ── Use persisted results for display (survives all subsequent re-runs) ─────────
if st.session_state["backtest_results"] is None:
    st.info(
        "Configure your portfolio and strategies in the sidebar, then click **▶ Run Backtest**."
    )
    st.stop()

results = st.session_state["backtest_results"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. NAV Comparison Chart
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Portfolio NAV Over Time")

fig = go.Figure()
for i, (label, r) in enumerate(results.items()):
    color = _PALETTE[i % len(_PALETTE)]
    fig.add_trace(go.Scatter(
        x=r["nav"].index,
        y=r["nav"].values,
        mode="lines",
        name=label,
        line=dict(color=color, width=1.8),
        hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra>" + label + "</extra>",
    ))

fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Portfolio Value ($)",
    yaxis_tickprefix="$",
    yaxis_tickformat=",.0f",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified",
    margin=dict(l=10, r=10, t=40, b=10),
    height=420,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Summary Metrics Table
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Strategy Comparison")

rows = []
for label, r in results.items():
    rows.append({
        "Strategy":          label,
        "Total Return":      f"{r['total_return']:+.2%}",
        "CAGR":              f"{r['cagr']:+.2%}",
        "Volatility":        f"{r['annualized_vol']:.2%}",
        "Sharpe":            f"{r['sharpe']:.3f}",
        "Max Drawdown":      f"{r['max_drawdown']:.2%}",
        "Rebalances":        r["rebalance_count"],
        "Trading Costs ($)": f"${r['costs_paid']:,.2f}",
        "Tax Paid ($)":      f"${r['tax_paid']:,.2f}",
    })

metrics_df = pd.DataFrame(rows).set_index("Strategy")
st.dataframe(metrics_df, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cost vs Volatility Scatter (size = total return)
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Cost vs. Volatility")
st.caption("Each point is one strategy. Size = total return (larger = higher return).")

_scatter_labels = list(results.keys())
_costs    = [results[l]["costs_paid"]        for l in _scatter_labels]
_vols     = [results[l]["annualized_vol"] * 100 for l in _scatter_labels]
_returns  = [results[l]["total_return"] * 100   for l in _scatter_labels]
_colors   = [_PALETTE[i % len(_PALETTE)]         for i in range(len(_scatter_labels))]

# Bubble size: scale so minimum is visible; use abs so negative returns still show
_min_size, _max_size = 12, 60
_ret_abs = [abs(r) for r in _returns]
_ret_range = max(_ret_abs) - min(_ret_abs) if max(_ret_abs) != min(_ret_abs) else 1
_sizes = [
    _min_size + (_max_size - _min_size) * (v - min(_ret_abs)) / _ret_range
    for v in _ret_abs
]

_sfig = go.Figure()
for i, label in enumerate(_scatter_labels):
    _sfig.add_trace(go.Scatter(
        x=[_costs[i]],
        y=[_vols[i]],
        mode="markers+text",
        name=label,
        marker=dict(size=_sizes[i], color=_colors[i], opacity=0.85,
                    line=dict(width=1, color="white")),
        text=[label],
        textposition="top center",
        textfont=dict(size=10),
        hovertemplate=(
            f"<b>{label}</b><br>"
            "Trading Costs: $%{x:,.2f}<br>"
            "Volatility: %{y:.2f}%<br>"
            f"Total Return: {_returns[i]:+.2f}%"
            "<extra></extra>"
        ),
    ))

_sfig.update_layout(
    xaxis_title="Total Trading Costs ($)",
    yaxis_title="Annualized Volatility (%)",
    xaxis=dict(tickprefix="$", tickformat=",.0f",
               showgrid=True, gridcolor="rgba(128,128,128,0.15)"),
    yaxis=dict(ticksuffix="%", tickformat=".2f",
               showgrid=True, gridcolor="rgba(128,128,128,0.15)"),
    showlegend=False,
    margin=dict(l=10, r=10, t=20, b=10),
    height=420,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(_sfig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Bar Charts
# ─────────────────────────────────────────────────────────────────────────────

labels_list = list(results.keys())
colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels_list))]

def _bar(y_vals, title, tickformat=",.3f", tickprefix=""):
    fig = go.Figure(go.Bar(
        x=labels_list, y=y_vals,
        marker_color=colors,
        hovertemplate="%{x}<br>" + tickprefix + "%{y:" + tickformat + "}<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        margin=dict(l=5, r=5, t=40, b=80),
        height=320,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis_tickangle=-30,
    )
    fig.update_yaxes(
        tickprefix=tickprefix, tickformat=tickformat,
        showgrid=True, gridcolor="rgba(128,128,128,0.15)",
    )
    return fig

bc1, bc2 = st.columns(2)
with bc1:
    st.plotly_chart(
        _bar(
            [results[l]["sharpe"] for l in labels_list],
            "Sharpe Ratio", tickformat=".3f",
        ),
        use_container_width=True,
    )
with bc2:
    st.plotly_chart(
        _bar(
            [results[l]["total_return"] * 100 for l in labels_list],
            "Total Return (%)", tickformat=".2f",
        ),
        use_container_width=True,
    )

bc3, bc4 = st.columns(2)
with bc3:
    st.plotly_chart(
        _bar(
            [results[l]["annualized_vol"] * 100 for l in labels_list],
            "Annualized Volatility (%)", tickformat=".2f",
        ),
        use_container_width=True,
    )
with bc4:
    st.plotly_chart(
        _bar(
            [results[l]["costs_paid"] for l in labels_list],
            "Total Trading Costs ($)", tickformat=",.2f", tickprefix="$",
        ),
        use_container_width=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Per-strategy trade detail expanders
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Trade & Gain Detail")

selected_strat = st.selectbox(
    "Select strategy to inspect",
    options=labels_list,
    index=0,
)

r = results[selected_strat]

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Total Trades",       len(r["trades_df"]))
col_b.metric("Rebalance Events",   r["rebalance_count"])
col_c.metric("Trading Costs",      f"${r['costs_paid']:,.2f}")
col_d.metric("Tax Paid",           f"${r['tax_paid']:,.2f}")

with st.expander("Trade Log"):
    tdf = r["trades_df"]
    if not tdf.empty:
        cost_cols = ["spread_cost", "slippage_cost", "fixed_cost", "variable_cost", "total_cost"]
        show_cols = [c for c in tdf.columns if c in
                     ["trade_date","ticker","action","shares","price","gross_value",
                      "net_cash_impact"] + cost_cols]
        st.dataframe(tdf[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No trades recorded.")

with st.expander("Realized Gains / Losses"):
    rdf = r["realized_df"]
    if not rdf.empty:
        st.dataframe(rdf, use_container_width=True, hide_index=True)
    else:
        st.info("No realized events.")
