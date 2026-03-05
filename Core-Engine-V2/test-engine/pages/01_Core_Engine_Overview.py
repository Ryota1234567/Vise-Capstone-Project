"""01 — Core Engine Overview"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
st.set_page_config(page_title="Core Engine Overview", page_icon="🏗️", layout="wide")

from ui_style import inject_site_css, render_hero, section_sep, section_header, render_footer
inject_site_css()

# ── Hero ──
render_hero(
    eyebrow="Portfolio Accounting Engine",
    title='Built on trades.<br>Not on <em>assumptions.</em>',
    subtitle="A transaction-driven engine for portfolio valuation, tax handling, and dividend reinvestment. Every dollar is traceable. Every gain is correctly taxed. Every price is real.",
    formula='Portfolio Value &nbsp;=&nbsp; <span>(Shares × Price)</span> &nbsp;+&nbsp; Cash',
)

# ── Section 1: The Problem ──
section_sep("01", "System Overview")
section_header(
    "The Problem",
    "Most portfolio models are wrong<br>from the start.",
    "Most simulations compound daily returns — multiply yesterday's value by today's price change. It's fast, but it can't answer the question that actually matters: <em>if I liquidated everything right now, what would I walk away with?</em>",
)

col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="vise-label" style="margin-bottom:0.5rem;">What most models do wrong</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="vise-principle" style="border-color: rgba(255,140,97,0.3);">
  <div class="vise-principle-icon" style="background:rgba(255,140,97,0.1);border-color:rgba(255,140,97,0.3);color:var(--accent3);">✕</div>
  <div>
    <div class="vise-principle-title" style="color:var(--accent3);">Inject dividends into return stream</div>
    <div class="vise-principle-body">Blurs price appreciation and cash received. Prevents lot-level tracking of DRIP shares.</div>
  </div>
</div>
<div class="vise-principle" style="border-color: rgba(255,140,97,0.3);">
  <div class="vise-principle-icon" style="background:rgba(255,140,97,0.1);border-color:rgba(255,140,97,0.3);color:var(--accent3);">✕</div>
  <div>
    <div class="vise-principle-title" style="color:var(--accent3);">Apply taxes as an end-of-year haircut</div>
    <div class="vise-principle-body">Ignores the timing effect of taxes on reinvestable cash throughout the year.</div>
  </div>
</div>
<div class="vise-principle" style="border-color: rgba(255,140,97,0.3);">
  <div class="vise-principle-icon" style="background:rgba(255,140,97,0.1);border-color:rgba(255,140,97,0.3);color:var(--accent3);">✕</div>
  <div>
    <div class="vise-principle-title" style="color:var(--accent3);">Average away transaction costs</div>
    <div class="vise-principle-body">Overstates returns and loses the slippage/commission signal in the cost basis.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="vise-label" style="margin-bottom:0.5rem;">What this engine does instead</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="vise-principle">
  <div class="vise-principle-icon">✓</div>
  <div>
    <div class="vise-principle-title">Every dollar traces to a trade</div>
    <div class="vise-principle-body">Nothing happens unless a trade executes. No phantom gains, no drift.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">✓</div>
  <div>
    <div class="vise-principle-title">Taxes deducted from cash immediately</div>
    <div class="vise-principle-body">The portfolio value shown is always the true after-tax number. No adjustment needed.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">✓</div>
  <div>
    <div class="vise-principle-title">Costs baked into cost basis</div>
    <div class="vise-principle-body">Slippage and commission increase the cost basis of each lot, reducing overstated gains.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

# ── Five Components ──
st.markdown('<div class="vise-label" style="margin-top:2rem;">The Five Components</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-card-grid">
  <div class="vise-card">
    <div class="vise-card-num">01</div>
    <div class="vise-card-title">Portfolio</div>
    <div><span class="vise-card-tag tag-stateful">Stateful</span></div>
    <p>The central ledger. Holds all state: lots, cash, trade history, realized gains, and taxes paid. Every other component reads from or writes to this object.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">02</div>
    <div class="vise-card-title">Tax Engine</div>
    <div><span class="vise-card-tag tag-stateless">Stateless</span></div>
    <p>A pure calculator. Given a gain amount and a holding period, returns the correct tax rate and amount owed.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">03</div>
    <div class="vise-card-title">Transaction Cost Engine</div>
    <div><span class="vise-card-tag tag-stateless">Stateless</span></div>
    <p>Another pure calculator. Given an action and a base price, returns execution price after slippage and all-in cash impact including commission.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">04</div>
    <div class="vise-card-title">Daily Valuation Engine</div>
    <div><span class="vise-card-tag tag-orchestrator">Orchestrator</span></div>
    <p>The outer loop. Iterates through every trading day, processes dividends, executes scheduled trades, and records the daily NAV snapshot.</p>
  </div>
  <div class="vise-card">
    <div class="vise-card-num">05</div>
    <div class="vise-card-title">Portfolio Reporter</div>
    <div><span class="vise-card-tag tag-stateless">Read-Only</span></div>
    <p>Takes the final Portfolio state and produces returns, tax summaries, gain breakdowns, turnover statistics, and a visualization dashboard.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── How Cash Moves ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">How Cash Moves</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-outputs">
  <div class="vise-output-item"><div class="vise-output-name" style="color:var(--accent)">BUY</div><div class="vise-output-desc">Cash out → −(shares × exec_price) − commission</div></div>
  <div class="vise-output-item"><div class="vise-output-name" style="color:var(--accent)">SELL</div><div class="vise-output-desc">Cash in → +(shares × exec_price) − commission</div></div>
  <div class="vise-output-item"><div class="vise-output-name" style="color:var(--accent)">DIVIDEND</div><div class="vise-output-desc">Cash in → tax out → +gross_div, then −(gross_div × dividend_rate)</div></div>
  <div class="vise-output-item"><div class="vise-output-name" style="color:var(--accent)">DRIP</div><div class="vise-output-desc">Cash out → −(drip_shares × drip_price) − commission</div></div>
  <div class="vise-output-item"><div class="vise-output-name" style="color:var(--accent)">CAPITAL GAINS</div><div class="vise-output-desc">Tax out → −(realized_gain × applicable_rate)</div></div>
</div>
""", unsafe_allow_html=True)

# ── Key Classes ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">Key Classes at a Glance</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-classref">
  <div class="vise-classref-title">class Portfolio</div>
  <div class="vise-classref-method"><div class="vise-crm-sig">buy(date, tid, ticker, shares, price)</div><div class="vise-crm-desc">Opens a new lot. Applies slippage + commission. Guards against insufficient cash.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">sell(date, tid, ticker, shares, price, lot_selection)</div><div class="vise-crm-desc">Disposes lots via FIFO/LIFO/TAX_OPTIMAL. Realizes gains, computes tax, deducts from cash.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">process_dividend(pay_date, tid, ticker, div_amount, price)</div><div class="vise-crm-desc">Full 6-step DRIP sequence: gross div → tax → log → deduct → DRIP buy → new lot.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">portfolio_value(price_lookup)</div><div class="vise-crm-desc">Returns market_value + cash. Recomputed from first principles on every call.</div></div>
</div>
<div class="vise-classref" style="border-left-color: var(--accent3);">
  <div class="vise-classref-title" style="color:var(--accent3);">class DailyValuationEngine</div>
  <div class="vise-classref-method"><div class="vise-crm-sig">__init__(portfolio, prices, dividends)</div><div class="vise-crm-desc">Builds the forward-filled price pivot table and pre-indexes dividends by pay date. All expensive setup happens here — once.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">run(start_date, end_date, scheduled_trades)</div><div class="vise-crm-desc">The outer loop. Iterates pd.bdate_range, processes dividends and trades, records NAV each day.</div></div>
</div>
""", unsafe_allow_html=True)

render_footer()
