# part2_pages.py — UI Pages (Passenger, Staff, Admin)
# This will be merged into app.py

# ── PAGE CONFIG & CSS ────────────────────────────────────────────────────────
PAGE_CSS = """
<style>
.block-container{padding-top:1.4rem!important}
.losti-header{background:linear-gradient(135deg,#0d1b4b 0%,#1a3a8f 55%,#2251cc 100%);
  border-radius:14px;padding:1.5rem 2rem;color:white;margin-bottom:1.5rem;
  box-shadow:0 4px 20px rgba(34,81,204,.3)}
.losti-header h1{margin:0;font-size:1.85rem}
.losti-header p{margin:.2rem 0 0;opacity:.8;font-size:.92rem}
.info-card{background:white;border-radius:12px;padding:1.1rem 1.4rem;
  box-shadow:0 2px 12px rgba(0,0,0,.07);border-left:5px solid #2251cc;margin-bottom:.9rem}
.firewall-badge{background:#fff0f0;border:1.5px solid #f5a0a0;border-radius:8px;
  padding:.5rem 1rem;font-size:.8rem;color:#b71c1c;font-weight:700;margin-bottom:1rem}
.pill{display:inline-block;padding:.18rem .7rem;border-radius:20px;
  font-size:.76rem;font-weight:700;letter-spacing:.04em}
.pill-searching{background:#fff3cd;color:#856404}
.pill-matched{background:#d1e7dd;color:#0a3622}
.pill-returned{background:#cfe2ff;color:#084298}
.pill-disposed{background:#fee2e2;color:#991b1b}
.pill-registered{background:#fce7f3;color:#9d174d}
.pill-identified{background:#ede9fe;color:#5b21b6}
.metric-box{background:white;border-radius:10px;padding:.85rem 1.1rem;
  box-shadow:0 2px 10px rgba(0,0,0,.07);text-align:center}
.metric-box .val{font-size:1.8rem;font-weight:700;color:#2251cc}
.metric-box .lbl{font-size:.76rem;color:#666;margin-top:.1rem}
.sidebar-brand{background:linear-gradient(135deg,#0d1b4b,#2251cc);
  border-radius:10px;padding:.9rem;color:white;text-align:center;margin-bottom:.9rem}
.sidebar-brand h2{margin:0;font-size:1.4rem}
.sidebar-brand p{margin:.15rem 0 0;font-size:.75rem;opacity:.8}
.data-table{width:100%;border-collapse:collapse;font-size:.85rem}
.data-table th{background:#0d1b4b;color:white;padding:.5rem .8rem;text-align:left}
.data-table td{padding:.45rem .8rem;border-bottom:1px solid #e9ecef;vertical-align:top}
.data-table tr:hover td{background:#f0f4ff}
.pay-card{background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:14px;
  padding:1.5rem;color:white;margin:1rem 0}
.pay-card h4{margin:0 0 .5rem;color:#e2e8f0}
</style>
"""

def header(title, subtitle=""):
    import streamlit as st
    st.markdown(f'<div class="losti-header"><h1>{title}</h1>'
                + (f'<p>{subtitle}</p>' if subtitle else "") + "</div>",
                unsafe_allow_html=True)

def pill(status):
    s = status.lower()
    cls = {"searching":"pill-searching","matched":"pill-matched",
           "returned":"pill-returned","disposed":"pill-disposed",
           "registered":"pill-registered","identified":"pill-identified"
           }.get(s, "pill-searching")
    return f'<span class="pill {cls}">{status.upper()}</span>'

def metric_strip(metrics):
    import streamlit as st
    cols = st.columns(len(metrics))
    for col,(val,lbl,icon) in zip(cols,metrics):
        col.markdown(f'<div class="metric-box"><div class="val">{icon} {val}</div>'
                     f'<div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)
