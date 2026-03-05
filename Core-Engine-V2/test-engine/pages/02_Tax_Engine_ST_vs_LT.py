"""02 — Tax Engine & ST/LT Classification"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
st.set_page_config(page_title="Tax Engine", page_icon="💰", layout="wide")

from ui_style import inject_site_css, section_sep, section_header, render_footer
inject_site_css()

section_sep("02", "Tax Engine")
section_header(
    "Tax Treatment",
    "Three categories.<br>One moment of truth.",
    "Taxes are deducted from cash the exact moment a gain is realized — not at year-end, not as a return adjustment. This keeps portfolio value accurate every day, because timing of tax payments affects reinvestable cash.",
)

# ── Tax Rate Cards ──
st.markdown("""
<div class="vise-tax-grid">
  <div class="vise-tax-card st">
    <div class="vise-tax-rate">35%</div>
    <div class="vise-tax-name">Short-Term Capital Gains</div>
    <div class="vise-tax-desc">Triggered when selling shares held for <strong>fewer than 365 days</strong>. Taxed at ordinary income rates. Frequent trading or early exits land here.</div>
  </div>
  <div class="vise-tax-card lt">
    <div class="vise-tax-rate">20%</div>
    <div class="vise-tax-name">Long-Term Capital Gains</div>
    <div class="vise-tax-desc">Triggered when selling shares held for <strong>365 days or more</strong>. Preferential rate. Holding one extra day past the threshold can change your tax bill materially.</div>
  </div>
  <div class="vise-tax-card div">
    <div class="vise-tax-rate">15%</div>
    <div class="vise-tax-name">Dividend Income</div>
    <div class="vise-tax-desc">Triggered on <strong>PAYDATE</strong> only. Applied to gross dividend before reinvestment. The after-tax amount is what gets reinvested via a DRIP trade.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Two Column: Classification + Losses ──
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="vise-label">Holding Period Classification</div>', unsafe_allow_html=True)
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.9rem;margin-bottom:1rem;line-height:1.7;">
Every lot carries an <code style="font-family:'DM Mono',monospace;font-size:0.82em;background:var(--surface2);border:1px solid var(--border);padding:0.1em 0.4em;border-radius:3px;color:var(--accent2);">open_date</code>. When the lot is sold, the engine computes holding days and routes the gain to the correct tax tier.
</p>
<div class="vise-code"><span class="cm"># Classification logic in TaxEngine</span>
holding_days = (sale_date - open_date).days

<span class="kw">if</span> holding_days >= <span class="s">365</span>:
    gain_type = <span class="s">'LT'</span>  <span class="cm"># 20% rate</span>
<span class="kw">else</span>:
    gain_type = <span class="s">'ST'</span>  <span class="cm"># 35% rate</span>

<span class="cm"># Happens at LOT level — same sell order
# can trigger both ST and LT events</span></div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="vise-label">Losses — Conservative Default</div>', unsafe_allow_html=True)
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.9rem;margin-bottom:1rem;line-height:1.7;">
The engine does not generate tax refunds for losing positions. A loss is recorded in the Realized Gains Ledger with a negative gain_loss value and tax_owed = 0.
</p>
<div class="vise-principle">
  <div class="vise-principle-icon">→</div>
  <div>
    <div class="vise-principle-title">Loss reduces reported realized gain</div>
    <div class="vise-principle-body">Visible in the Realized Gains Ledger and gains summary report.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">→</div>
  <div>
    <div class="vise-principle-title">No positive cash event on a loss</div>
    <div class="vise-principle-body">Extend TaxEngine.compute_sale_tax for loss carry-forward logic if needed.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

# ── Class Reference ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">How TaxEngine Works in Code</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-classref">
  <div class="vise-classref-title">class TaxEngine · stateless — no memory between calls</div>
  <div class="vise-classref-method"><div class="vise-crm-sig">classify_holding(open_date, close_date)</div><div class="vise-crm-desc">Computes (close_date − open_date).days. Returns ('LT', 0.20) if ≥ 365, else ('ST', 0.35). Called once per lot during sell().</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">compute_sale_tax(gain, gain_type)</div><div class="vise-crm-desc">If gain < 0, adds abs(gain) to the ST or LT carry-forward bucket and returns 0. If gain > 0, nets it against same-type carry-forward first, then cross-type, then taxes the remainder.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">compute_dividend_tax(gross_dividend)</div><div class="vise-crm-desc">Returns (tax_owed, after_tax_div). Simple flat-rate multiply. Called inside Portfolio.process_dividend() before the DRIP reinvestment.</div></div>
  <div class="vise-classref-method"><div class="vise-crm-sig">st_loss_carryforward · lt_loss_carryforward</div><div class="vise-crm-desc">Two float attributes that persist across the full simulation. Reset to 0 on Portfolio construction.</div></div>
</div>
<p style="font-size:0.82rem;color:var(--text-muted);margin-top:0.75rem;line-height:1.6;">
TaxEngine is instantiated inside Portfolio.__init__ and stored as self.tax_eng. You never call it directly — Portfolio.sell() and Portfolio.process_dividend() call it internally on every realization event.
</p>
""", unsafe_allow_html=True)

render_footer()
