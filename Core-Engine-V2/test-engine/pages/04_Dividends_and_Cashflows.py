"""04 — Dividends & Cash Flows"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
st.set_page_config(page_title="Dividends & Cashflows", page_icon="💵", layout="wide")

from ui_style import inject_site_css, section_sep, section_header, render_footer
inject_site_css()

section_sep("05", "Dividend Handling")
section_header(
    "DRIP Sequence",
    "Dividends trigger on PAYDATE.<br>Not before. Not differently.",
    "Three mistakes plague most dividend models: reinvesting on ex-date, injecting dividends into the return stream, and adjusting prices. This engine avoids all three. Dividends are cash events that create new trades — nothing else.",
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
<div class="vise-steps">
  <div class="vise-step"><div class="vise-step-num">1</div><div><div class="vise-step-title">Count shares held</div><div class="vise-step-detail">Sum open lot shares for this security as of PAYDATE. This is the entitled count.</div></div></div>
  <div class="vise-step"><div class="vise-step-num">2</div><div><div class="vise-step-title">Compute gross dividend</div><div class="vise-step-detail">shares_held × DIVAMOUNT</div></div></div>
  <div class="vise-step"><div class="vise-step-num">3</div><div><div class="vise-step-title">Apply dividend tax</div><div class="vise-step-detail">tax = gross_div × 0.15<br>after_tax = gross_div − tax</div></div></div>
  <div class="vise-step"><div class="vise-step-num">4</div><div><div class="vise-step-title">Log realization event</div><div class="vise-step-detail">Written to Realized Gains Ledger as a DIVIDEND event with full detail.</div></div></div>
  <div class="vise-step"><div class="vise-step-num">5</div><div><div class="vise-step-title">Deduct tax from cash</div><div class="vise-step-detail">+gross_div added to cash, then −tax deducted. Net: +after_tax_div in cash.</div></div></div>
  <div class="vise-step"><div class="vise-step-num">6</div><div><div class="vise-step-title">Execute DRIP buy</div><div class="vise-step-detail">drip_shares = after_tax_div ÷ reinvest_price<br>Goes through full cost engine. <strong>Creates a new lot</strong> with today as open_date.</div></div></div>
</div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="vise-label">Why DRIP Creates a New Lot</div>', unsafe_allow_html=True)
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:1.25rem;line-height:1.7;">The reinvestment does not add shares to an existing lot. It opens a brand new one — with today's price as cost basis and today as the open date.</p>
<div class="vise-principle">
  <div class="vise-principle-icon">→</div>
  <div>
    <div class="vise-principle-title">Different cost basis</div>
    <div class="vise-principle-body">DRIP shares cost today's price, not the original purchase price. Gains are computed correctly when sold.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">→</div>
  <div>
    <div class="vise-principle-title">Different holding period clock</div>
    <div class="vise-principle-body">The 365-day LT threshold starts from the DRIP date, independent of the original position.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">→</div>
  <div>
    <div class="vise-principle-title">Quarterly dividends spawn many lots</div>
    <div class="vise-principle-body">Over a multi-year hold, a single original buy can produce 8–12 DRIP lots. Each tracked separately.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

# ── Code Reference ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">How Dividends Work in Code</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-classref">
  <div class="vise-classref-title">Portfolio.process_dividend(pay_date, tradingitemid, tickersymbol, div_amount_per_share, reinvest_price)</div>
  <div class="vise-classref-method"><div class="vise-crm-sig">Step 1–2: _shares_held + gross div</div><div class="vise-crm-desc">_shares_held(tradingitemid) sums open lot shares from _lots_idx. If 0, silently returns. Gross = shares × div_amount_per_share.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">Step 3–4: TaxEngine + realized ledger</div><div class="vise-crm-desc">Calls tax_eng.compute_dividend_tax(gross_div) → (tax_owed, after_tax_div). Logs a DIVIDEND event to realized_ledger.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">Step 5–6: Cash + DRIP buy</div><div class="vise-crm-desc">Adds gross to cash, deducts tax. Then calls buy(source='DRIP') with after_tax_div ÷ reinvest_price shares. This opens a new lot.</div></div>
</div>
<div class="vise-classref" style="border-left-color:var(--accent3);margin-top:0.75rem;">
  <div class="vise-classref-title" style="color:var(--accent3);">DailyValuationEngine — dividend triggering</div>
  <div class="vise-classref-method"><div class="vise-crm-sig">self._div_by_date</div><div class="vise-crm-desc">A dict built once in __init__: {PAYDATE → [list of dividend row dicts]}. The daily loop calls _get_dividends_on(day) which is a pure .get() — O(1) per day.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">Dividend data source</div><div class="vise-crm-desc">Must contain TRADINGITEMID, PAYDATE, DIVAMOUNT. Only securities in TRADING_IDS are kept after loading. The engine checks PAYDATE — not EXDATE.</div></div>
</div>
""", unsafe_allow_html=True)

render_footer()
