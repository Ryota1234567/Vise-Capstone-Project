"""05 — Valuation, Reporting & Performance"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
st.set_page_config(page_title="Valuation & Performance", page_icon="📊", layout="wide")

from ui_style import inject_site_css, section_sep, section_header, render_footer
inject_site_css()

# ═══════════════════════════════════════════════════════════
# SECTION: Daily Valuation
# ═══════════════════════════════════════════════════════════
section_sep("06", "Daily Valuation")
section_header(
    "The Daily Loop",
    "Four steps. Every business day.<br>No look-ahead, ever.",
    "The Daily Valuation Engine iterates through every business day. Each day executes in a fixed sequence — the order matters because DRIP shares must be visible in the same day's valuation.",
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
<div class="vise-principle">
  <div class="vise-principle-icon" style="font-size:0.65rem;font-weight:500;">01</div>
  <div>
    <div class="vise-principle-title">Build price lookup</div>
    <div class="vise-principle-body">Filter prices to PRICEDATE ≤ today, take last per security. Future prices are invisible.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon" style="font-size:0.65rem;font-weight:500;">02</div>
  <div>
    <div class="vise-principle-title">Process dividends</div>
    <div class="vise-principle-body">Check for PAYDATE == today. Execute the full 6-step DRIP sequence for each match.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon" style="font-size:0.65rem;font-weight:500;">03</div>
  <div>
    <div class="vise-principle-title">Execute scheduled trades</div>
    <div class="vise-principle-body">Check the user-provided trade schedule for orders dated today. Buys and sells routed through the full accounting pipeline.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon" style="font-size:0.65rem;font-weight:500;">04</div>
  <div>
    <div class="vise-principle-title">Record NAV snapshot</div>
    <div class="vise-principle-body">Compute market value + cash, unrealized gain, realized YTD, taxes YTD, and daily return.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
<div class="vise-formula-visual">
  <div class="vise-formula-big">
    <em>Portfolio Value</em><br>= <span>(Shares × Price)</span> + Cash
  </div>
  <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.5rem;">Recomputed from first principles every day. Never carries forward yesterday's value.</div>
</div>
<div style="padding:1rem 1.25rem;background:var(--surface);border:1px solid rgba(79,255,176,0.2);border-radius:6px;">
  <div class="vise-label" style="margin-bottom:0.4rem;">Daily Return Is Already After-Tax</div>
  <p style="font-size:0.84rem;color:var(--text-muted);line-height:1.65;">Because taxes hit cash at the moment of realization, portfolio value on Day N already reflects that reduction. No separate after-tax adjustment needed. The NAV time series <em>is</em> the after-tax time series.</p>
</div>
    """, unsafe_allow_html=True)

# ── Edge Cases ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">Edge Cases & Guardrails</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-guardrails">
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Sell > shares held</div><div class="vise-guardrail-response">Order <strong>clamped to available shares</strong>. Warning emitted. No crash.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Insufficient cash for buy</div><div class="vise-guardrail-response">Trade <strong>skipped with warning</strong>. Cash cannot go negative.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Transaction costs > proceeds</div><div class="vise-guardrail-response">Sell <strong>aborted with warning</strong>. No negative cash event created.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">No price on dividend pay date</div><div class="vise-guardrail-response">Uses <strong>last available close</strong>. Weekend/holiday paydates handled automatically.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Zero shares at dividend time</div><div class="vise-guardrail-response">Dividend <strong>silently skipped</strong>. Position was already sold.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Sell entire position</div><div class="vise-guardrail-response">Pass shares=1e9. <strong>Disposal loop exhausts all lots</strong> and stops naturally.</div></div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SECTION: Reporting
# ═══════════════════════════════════════════════════════════
section_sep("07", "Reporting")
section_header(
    "Outputs",
    "Five views of the truth.<br>All traceable to the ledger.",
    "The Portfolio Reporter is read-only — it never modifies state. Every number it reports can be reproduced by querying the underlying ledgers directly.",
)

st.markdown("""
<div class="vise-outputs">
  <div class="vise-output-item"><div class="vise-output-name">NAV Summary</div><div class="vise-output-desc">Full daily time series with portfolio value, cash, market value, daily return, and cumulative return. One row per trading day.</div></div>
  <div class="vise-output-item"><div class="vise-output-name">After-Tax Return</div><div class="vise-output-desc">A single percentage: (final_value ÷ initial_value) − 1. Already net of all taxes and costs.</div></div>
  <div class="vise-output-item"><div class="vise-output-name">Tax Summary</div><div class="vise-output-desc">Total taxes paid broken down by category: short-term gains, long-term gains, and dividend tax.</div></div>
  <div class="vise-output-item"><div class="vise-output-name">Gains Summary</div><div class="vise-output-desc">Total realized gain/loss, current unrealized gain, total taxes paid, and net after-tax realized gain.</div></div>
  <div class="vise-output-item"><div class="vise-output-name">Turnover Stats</div><div class="vise-output-desc">Buy count, sell count, DRIP count, total buy and sell volumes, and total commissions paid.</div></div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SECTION: Configuration
# ═══════════════════════════════════════════════════════════
section_sep("08", "Configuration")
section_header(
    "Two Dictionaries",
    "All levers in one place.<br>Change once, flows everywhere.",
    "Every configurable parameter lives at the top of the notebook. There is no hunting through class constructors or method signatures.",
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("""
<div class="vise-config-block">
  <div class="vise-config-header">TAX_CONFIG</div>
  <div class="vise-config-row"><div class="vise-config-key">short_term_rate</div><div class="vise-config-val">0.35</div><div class="vise-config-desc">Gains from positions held < 365 days</div></div>
  <div class="vise-config-row"><div class="vise-config-key">long_term_rate</div><div class="vise-config-val">0.20</div><div class="vise-config-desc">Gains from positions held ≥ 365 days</div></div>
  <div class="vise-config-row"><div class="vise-config-key">dividend_rate</div><div class="vise-config-val">0.15</div><div class="vise-config-desc">Tax on gross dividend before reinvestment</div></div>
  <div class="vise-config-row"><div class="vise-config-key">lt_holding_days</div><div class="vise-config-val">365</div><div class="vise-config-desc">Day threshold between ST and LT</div></div>
</div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown("""
<div class="vise-config-block">
  <div class="vise-config-header">COST_CONFIG</div>
  <div class="vise-config-row"><div class="vise-config-key">commission_per_share</div><div class="vise-config-val">$0.005</div><div class="vise-config-desc">Flat dollar fee per share, every trade</div></div>
  <div class="vise-config-row"><div class="vise-config-key">slippage_bps</div><div class="vise-config-val">5 bps</div><div class="vise-config-desc">Adverse price movement at execution</div></div>
</div>
    """, unsafe_allow_html=True)

# ── Common Configurations ──
st.markdown('<div class="vise-label" style="margin-top:1rem;">Common Configurations</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-guardrails">
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Tax-deferred account (IRA / 401k)</div><div class="vise-guardrail-response">Set short_term_rate, long_term_rate, and dividend_rate all to <strong>0</strong>.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Commission-free brokerage</div><div class="vise-guardrail-response">Set commission_per_share to <strong>0</strong>. Keep slippage.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Everything long-term</div><div class="vise-guardrail-response">Set lt_holding_days to <strong>0</strong>. All gains taxed at 20%.</div></div>
  <div class="vise-guardrail"><div class="vise-guardrail-trigger">Institutional slippage</div><div class="vise-guardrail-response">Increase slippage_bps to <strong>10–20</strong> for large-order realism.</div></div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SECTION: Performance
# ═══════════════════════════════════════════════════════════
section_sep("10", "Performance")
section_header(
    "Optimizations",
    "Built for large price files<br>and long simulations.",
    "Four targeted fixes eliminate the bottlenecks that make the engine slow at scale — particularly with a large prices CSV, 20–50 securities, and a 10+ year simulation window.",
)

st.markdown("""
<div class="vise-card-grid">
  <div class="vise-card">
    <div class="vise-card-num">01</div>
    <div class="vise-card-title">Security Filter</div>
    <div><span class="vise-card-tag tag-stateless">Data Loading</span></div>
    <p>Set TRADING_IDS to only the securities you trade. A 3M-row file covering 5,000 stocks cut to 50 securities drops to ~30,000 rows — <strong>99% smaller</strong>.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">02</div>
    <div class="vise-card-title">Pre-Built Price Table</div>
    <div><span class="vise-card-tag tag-orchestrator">Daily Loop</span></div>
    <p>Forward-filled pivot table built once in __init__. Each day's lookup is a single <strong>O(1) .loc[] row access</strong>. Over 2,500 days that's 2,500 expensive operations → 2,500 dict lookups.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">03</div>
    <div class="vise-card-title">List-Based Ledger Buffers</div>
    <div><span class="vise-card-tag tag-stateful">Portfolio</span></div>
    <p>Six ledgers previously used pd.concat row-by-row. Now accumulates rows as plain dicts in a list, materializes to DataFrame once. Eliminates the <strong>O(n²) memory pattern</strong>.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">04</div>
    <div class="vise-card-title">Lot Index + Reverse Map</div>
    <div><span class="vise-card-tag tag-stateful">Portfolio</span></div>
    <p>_lots_idx (security → lot positions) for O(k) lookup, and _lot_id_to_buf for O(1) sell updates. Critical for 50 securities with quarterly dividends over 10 years.</p>
  </div>
</div>
""", unsafe_allow_html=True)

render_footer()
