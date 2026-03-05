"""03 — Sell Handling & Tax-Loss Harvesting"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
st.set_page_config(page_title="Sell Handling & TLH", page_icon="📉", layout="wide")

from ui_style import inject_site_css, section_sep, section_header, render_footer
inject_site_css()

section_sep("03", "Sell Handling")
section_header(
    "Lot Selection & Tax-Aware Selling",
    "Which shares you sell matters<br>as much as when you sell.",
    "When you hold multiple lots of the same stock at different cost bases, you get to choose which ones to sell. That choice directly changes your tax bill. The engine supports three strategies — set per sell order via <code style='font-family:DM Mono,monospace;font-size:0.82em;background:#1a1f2e;border:1px solid #232a3a;padding:0.1em 0.4em;border-radius:3px;color:#7b8cff;'>lot_selection</code>.",
)

# ── Three Mode Cards ──
st.markdown("""
<div class="vise-tax-grid" style="margin-bottom:2rem;">
  <div class="vise-tax-card" style="border-top:2px solid var(--accent2);">
    <div class="vise-tax-rate" style="font-size:1.3rem;color:var(--accent2);margin-bottom:0.4rem;">FIFO</div>
    <div class="vise-tax-name">First In, First Out</div>
    <div class="vise-tax-desc">Always sells the <strong>oldest lot first</strong>. Simple and predictable. Oldest lots are most likely to be long-term (20% rate), so FIFO tends to favour lower tax rates — but it ignores loss opportunities.</div>
  </div>
  <div class="vise-tax-card" style="border-top:2px solid var(--text-muted);">
    <div class="vise-tax-rate" style="font-size:1.3rem;color:var(--text-muted);margin-bottom:0.4rem;">LIFO</div>
    <div class="vise-tax-name">Last In, First Out</div>
    <div class="vise-tax-desc">Always sells the <strong>newest lot first</strong>. Keeps old low-basis lots alive longer, deferring their eventual gain further into the future.</div>
  </div>
  <div class="vise-tax-card lt">
    <div class="vise-tax-rate" style="font-size:1rem;margin-bottom:0.4rem;">TAX_OPTIMAL</div>
    <div class="vise-tax-name">Tax-Loss Harvesting</div>
    <div class="vise-tax-desc">Sells <strong>loss lots first</strong> (biggest ST loss first, then LT losses), then smallest-gain lots last. Crystallises losses into a carry-forward that offsets future gains.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── The Key Scenario ──
st.markdown('<div class="vise-label">The Scenario That Motivated This</div>', unsafe_allow_html=True)
st.markdown("""
<div class="vise-example-box" style="margin-bottom:2rem;">
  <div style="padding:1.5rem;font-family:'DM Mono',monospace;font-size:0.78rem;color:var(--text-dim);letter-spacing:0.1em;text-transform:uppercase;border-bottom:1px solid var(--border);">You hold two lots. Current price is $150. Which do you sell?</div>
  <div style="padding:1.25rem 1.5rem;">
    <div style="display:flex;gap:1rem;align-items:center;padding:0.6rem 0.75rem;border-radius:4px;background:rgba(79,255,176,0.06);border:1px solid rgba(79,255,176,0.2);margin-bottom:0.5rem;font-family:'DM Mono',monospace;font-size:0.82rem;">
      <span style="color:var(--text-dim);font-size:0.72rem;">LOT001</span>
      <span style="color:var(--text-muted);flex:1;">2 years ago · cost $100</span>
      <span style="color:var(--heading);">+$50 gain / share</span>
      <span style="font-size:0.62rem;padding:0.15rem 0.5rem;border-radius:3px;background:rgba(79,255,176,0.15);color:var(--accent);">LT</span>
      <span style="font-size:0.72rem;color:var(--accent);">tax = $10/sh</span>
    </div>
    <div style="display:flex;gap:1rem;align-items:center;padding:0.6rem 0.75rem;border-radius:4px;background:rgba(255,140,97,0.06);border:1px solid rgba(255,140,97,0.2);font-family:'DM Mono',monospace;font-size:0.82rem;">
      <span style="color:var(--text-dim);font-size:0.72rem;">LOT002</span>
      <span style="color:var(--text-muted);flex:1;">6 months ago · cost $200</span>
      <span style="color:var(--heading);">−$50 loss / share</span>
      <span style="font-size:0.62rem;padding:0.15rem 0.5rem;border-radius:3px;background:rgba(255,140,97,0.15);color:var(--accent3);">ST</span>
      <span style="font-size:0.72rem;color:var(--accent3);">tax = $0/sh</span>
    </div>
  </div>
  <div style="padding:1rem 1.5rem;border-top:1px solid var(--border);font-size:0.82rem;color:var(--text-muted);line-height:1.8;">
    <strong style="color:var(--heading);">FIFO sells LOT001</strong> — realises a $50 LT gain, pays $10/share in tax. You keep the loss lot, but you've paid tax now.<br>
    <strong style="color:var(--accent);">TAX_OPTIMAL sells LOT002</strong> — realises a $50 ST loss, pays $0 tax, and banks that $50 loss as a carry-forward that will reduce tax on the next gain you realise.
  </div>
</div>
""", unsafe_allow_html=True)

# ── Loss Carry-Forward ──
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="vise-label">Loss Carry-Forward</div>', unsafe_allow_html=True)
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:1rem;line-height:1.7;">Harvested losses don't disappear — they go into a carry-forward bucket (separate ST and LT balances) that automatically offsets the next gain before tax is computed.</p>
<div class="vise-code"><span class="cm"># When a loss is realised:</span>
st_loss_carryforward += abs(loss)  <span class="cm"># or lt_</span>

<span class="cm"># When the next gain arrives:</span>
taxable = gain - st_loss_carryforward
<span class="cm"># carryforward is consumed, remainder taxed
# ST losses offset ST gains first (35% rate)
# then spill into LT gains (20% rate)</span></div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="vise-label">Netting Priority</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="vise-principle">
  <div class="vise-principle-icon" style="color:var(--accent3);background:rgba(255,140,97,0.1);border-color:rgba(255,140,97,0.3);">ST</div>
  <div>
    <div class="vise-principle-title">ST losses → ST gains first</div>
    <div class="vise-principle-body">Offsets gains taxed at 35% — highest value use. Excess spills into LT gains.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon" style="color:var(--accent);background:rgba(79,255,176,0.1);border-color:rgba(79,255,176,0.3);">LT</div>
  <div>
    <div class="vise-principle-title">LT losses → LT gains first</div>
    <div class="vise-principle-body">Offsets gains taxed at 20%. Excess spills into ST gains.</div>
  </div>
</div>
<div class="vise-principle">
  <div class="vise-principle-icon">∞</div>
  <div>
    <div class="vise-principle-title">Carry-forward persists</div>
    <div class="vise-principle-body">Unused losses accumulate across the full simulation. Inspect anytime via pf.tax_eng.st_loss_carryforward.</div>
  </div>
</div>
    """, unsafe_allow_html=True)

# ── Cost Basis Formulas ──
st.markdown('<div class="vise-label" style="margin-top:1.5rem;">Cost Basis & Realized Gain Formulas</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:0.75rem;line-height:1.7;">Cost basis is the all-in acquisition cost — not just the closing price:</p>
<div class="vise-code">exec_price = close_price * (<span class="s">1</span> + slippage_bps / <span class="s">10000</span>)
commission  = shares * commission_per_share

cost_basis = (shares * exec_price + commission) / shares
<span class="cm"># cost_basis > close_price — reduces overstated gains</span></div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown("""
<p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:0.75rem;line-height:1.7;">On sale, proceeds are also net of costs:</p>
<div class="vise-code">sell_exec    = close_price * (<span class="s">1</span> - slippage_bps / <span class="s">10000</span>)
net_proceeds = shares * sell_exec - commission

gain = net_proceeds - (shares * cost_basis)
tax  = <span class="fn">compute_sale_tax</span>(gain, gain_type)
<span class="cm"># loss? → added to carry-forward, tax = 0</span></div>
    """, unsafe_allow_html=True)

render_footer()
