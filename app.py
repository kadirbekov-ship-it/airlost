
# =============================================================================
# part1_core.py — Database, PDF, Auth
# =============================================================================
import os, io, hashlib, base64, difflib
from datetime import datetime, date, timedelta

import streamlit as st
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    Float, DateTime, ForeignKey, Text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/found_photos", exist_ok=True)
os.makedirs("acts", exist_ok=True)

# ── DATABASE ─────────────────────────────────────────────────────────────────
Base = declarative_base()
engine = create_engine("sqlite:///losty.db",
                        connect_args={"check_same_thread": False}, echo=False)
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    username      = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role          = Column(String(20), nullable=False)   # staff | super_admin
    fio           = Column(String(120))
    created_at    = Column(DateTime, default=datetime.utcnow)


class LostClaim(Base):
    __tablename__ = "lost_claims"
    id              = Column(Integer, primary_key=True)
    l_number        = Column(String(20), unique=True, nullable=False)
    # Identity & Contact
    passenger_name  = Column(String(120), nullable=False)
    passport_data   = Column(String(80), nullable=False)
    phone           = Column(String(40))
    email           = Column(String(120))
    # Travel Info
    arrival_flight  = Column(String(60))
    arrival_date    = Column(String(30))
    transit_flight  = Column(String(60))
    boarding_pass   = Column(String(60))
    baggage_tag     = Column(String(60))
    # Item
    location_lost   = Column(String(250))
    description     = Column(Text, nullable=False)
    estimated_value = Column(Float, default=0.0)
    image_path      = Column(String(350))
    # 5-Rule & Storage
    rules_accepted  = Column(Boolean, default=False)
    storage_choice  = Column(String(20), default="service")  # org($20) | service($5)
    # Financial — HIDDEN from staff
    fee_paid        = Column(Boolean, default=False)       # $10
    commission_paid = Column(Boolean, default=False)       # $20 + 10% reward
    reward_amount   = Column(Float, default=0.0)
    # Status
    status          = Column(String(30), default="Searching")
    found_item_id   = Column(Integer, ForeignKey("found_items.id"), nullable=True)
    found_item      = relationship("FoundItem", back_populates="claims")
    act_pdf_path    = Column(String(350))
    created_at      = Column(DateTime, default=datetime.utcnow)


class FoundItem(Base):
    __tablename__ = "found_items"
    id            = Column(Integer, primary_key=True)
    f_number      = Column(String(20), unique=True, nullable=False)
    description   = Column(Text, nullable=False)
    location_found= Column(String(250))
    finder_name   = Column(String(250))
    flight_number = Column(String(60))
    image_path1   = Column(String(350))
    image_path2   = Column(String(350))
    image_path3   = Column(String(350))
    
    # ПРОВЕРЬ ЭТУ СТРОКУ, ОНА ДОЛЖНА БЫТЬ:
    status        = Column(String(30), default="registered")
    
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_by    = relationship("User")
    
    claims        = relationship("LostClaim", back_populates="found_item",
                                 foreign_keys=[LostClaim.found_item_id])
    
    created_at    = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    user_fio   = Column(String(120))
    action     = Column(String(50))
    detail     = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _next_f():
    s = Session()
    n = s.query(FoundItem).count() + 1
    s.close()
    yr = datetime.now().year
    return f"F-{yr}-{n:04d}"

def _next_l():
    s = Session()
    n = s.query(LostClaim).count() + 1
    s.close()
    yr = datetime.now().year
    return f"L-{yr}-{n:04d}"

def _save_upload(upload, prefix):
    ext = upload.name.rsplit(".", 1)[-1]
    path = f"uploads/{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    img = Image.open(upload)
    img.thumbnail((1200, 1200), Image.LANCZOS)
    img.save(path, optimize=True, quality=85)
    return path

def _save_bytes(raw_bytes, prefix, ext="jpg"):
    path = f"uploads/found_photos/{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    pil = Image.open(io.BytesIO(raw_bytes))
    pil.thumbnail((1400, 1400), Image.LANCZOS)
    pil.save(path, optimize=True, quality=87)
    return path

def audit(action, detail=""):
    s = Session()
    s.add(AuditLog(
        user_id=st.session_state.get("user_id"),
        user_fio=st.session_state.get("fio", "System"),
        action=action, detail=detail))
    s.commit(); s.close()

def ai_similarity(loc_lost, loc_found, desc_lost, desc_found):
    """Simple similarity score between lost/found items."""
    s1 = difflib.SequenceMatcher(None, (loc_lost or "").lower(),
                                  (loc_found or "").lower()).ratio()
    s2 = difflib.SequenceMatcher(None, (desc_lost or "").lower(),
                                  (desc_found or "").lower()).ratio()
    return round((s1 * 0.4 + s2 * 0.6) * 100, 1)

def init_db():
    Base.metadata.create_all(engine)
    s = Session()
    if not s.query(User).filter_by(username="admin").first():
        s.add(User(username="admin", password_hash=_hash("admin123"),
                   role="super_admin", fio="Super Administrator"))
    s.commit(); s.close()

init_db()

# ── PDF STYLES ───────────────────────────────────────────────────────────────
C_NAVY  = colors.HexColor("#0d1b4b")
C_BLUE  = colors.HexColor("#2251cc")
C_LTBL  = colors.HexColor("#eef2ff")
C_GRAY  = colors.HexColor("#6b7280")
C_DARK  = colors.HexColor("#374151")
C_GREEN = colors.HexColor("#15803d")
C_RED   = colors.HexColor("#dc2626")

def ps(name, **kw):
    return ParagraphStyle(name, **kw)

SH1  = ps("h1",  fontName="Helvetica-Bold",   fontSize=15, alignment=TA_CENTER, textColor=C_NAVY, spaceAfter=2)
SH2  = ps("h2",  fontName="Helvetica-Bold",   fontSize=11, alignment=TA_CENTER, textColor=C_BLUE, spaceAfter=5)
SSUB = ps("sub", fontName="Helvetica",         fontSize=9,  alignment=TA_CENTER, textColor=C_GRAY, spaceAfter=4)
SNM  = ps("nm",  fontName="Helvetica",         fontSize=9,  leading=12)
SBLD = ps("bld", fontName="Helvetica-Bold",    fontSize=9,  leading=12)
SFTR = ps("ftr", fontName="Helvetica-Oblique", fontSize=7.5, alignment=TA_CENTER, textColor=C_GRAY)
SSIG = ps("sig", fontName="Helvetica",         fontSize=8.5, alignment=TA_CENTER, leading=13)
SIGB = ps("sigb",fontName="Helvetica-Bold",    fontSize=8.5, alignment=TA_CENTER)
SWRN = ps("wrn", fontName="Helvetica-Oblique", fontSize=8,  textColor=C_GRAY, leading=11)


def _sec_table(label, rows, hdr_col):
    data = [[Paragraph(label, ps("th", fontName="Helvetica-Bold", fontSize=9,
                                 textColor=colors.white)), ""]]
    data += [[Paragraph(k, SBLD), Paragraph(str(v), SNM)] for k, v in rows]
    t = Table(data, colWidths=[5.2*cm, 11.6*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(1,0),hdr_col),("SPAN",(0,0),(1,0)),
        ("ALIGN",(0,0),(-1,-1),"LEFT"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_LTBL,colors.white]),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    return t


def generate_return_act(claim, found, staff_name) -> bytes:
    buf = io.BytesIO()
    fname_disk = f"acts/ReturnAct_{claim.l_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = [
        Paragraph("✈  LOSTY PLATFORM", SH1),
        Paragraph("AIRPORT LOST &amp; FOUND SERVICE", SH2),
        HRFlowable(width="100%", thickness=2, color=C_NAVY, spaceAfter=6),
        Paragraph(f"RETURN ACT &nbsp;|&nbsp; <b>ACT-{claim.l_number}</b>"
                  f" &nbsp;|&nbsp; Date: <b>{datetime.now().strftime('%d %B %Y')}</b>", SSUB),
        Spacer(1, .4*cm),
        _sec_table("PASSENGER IDENTITY", [
            ("Full Name", claim.passenger_name),
            ("Passport Data", claim.passport_data or "—"),
            ("Phone", claim.phone or "—"),
            ("Email", claim.email or "—"),
        ], C_NAVY),
        Spacer(1, .3*cm),
        _sec_table("TRAVEL INFORMATION", [
            ("Arrival Flight", f"{claim.arrival_flight or '—'} / {claim.arrival_date or '—'}"),
            ("Transit Flight", claim.transit_flight or "—"),
            ("Boarding Pass", claim.boarding_pass or "—"),
            ("Baggage Tag", claim.baggage_tag or "—"),
        ], C_BLUE),
        Spacer(1, .3*cm),
        _sec_table("FOUND ITEM DETAILS", [
            ("Found-Item ID", found.f_number),
            ("Description", (found.description or "")[:120]),
            ("Location Found", found.location_found or "—"),
            ("Finder", found.finder_name or "—"),
            ("Registered", found.created_at.strftime("%d %B %Y")),
        ], C_DARK),
        Spacer(1, .3*cm),
        _sec_table("ITEM AS REPORTED", [
            ("Claim ID", claim.l_number),
            ("Location Lost", claim.location_lost or "—"),
            ("Description", (claim.description or "")[:120]),
            ("Estimated Value", f"${claim.estimated_value:.2f}"),
            ("Storage", "Organisation ($20)" if claim.storage_choice == "org" else "Service ($5)"),
        ], C_GREEN),
        Spacer(1, .3*cm),
        Paragraph("The passenger hereby confirms receipt of the above-described item. "
                  "This Return Act constitutes official confirmation of property restitution.", SWRN),
        Spacer(1, .5*cm),
    ]
    sig_data = [
        [Paragraph("SIGNATURES &amp; OFFICIAL STAMP",
                   ps("sh", fontName="Helvetica-Bold", fontSize=9,
                      textColor=colors.white, alignment=TA_CENTER)), "", ""],
        [Paragraph("AIRPORT STAFF", SIGB),
         Paragraph("CUSTOMS STAMP", SIGB),
         Paragraph("PASSENGER", SIGB)],
        [Paragraph("\n\n\n", SSIG), Paragraph("\n\n\n", SSIG), Paragraph("\n\n\n", SSIG)],
        [Paragraph(f"Name:&nbsp; {staff_name}", SSIG),
         Paragraph("[ Official Stamp ]",
                   ps("stmp", fontName="Helvetica-BoldOblique", fontSize=9,
                      textColor=C_BLUE, alignment=TA_CENTER)),
         Paragraph(f"Name:&nbsp; {claim.passenger_name}", SSIG)],
        [Paragraph("Signature: _______________", SSIG), "",
         Paragraph("Signature: _______________", SSIG)],
        [Paragraph("Date: _______________", SSIG), "",
         Paragraph("Date: _______________", SSIG)],
    ]
    sig_t = Table(sig_data, colWidths=[5.6*cm, 5.6*cm, 5.6*cm])
    sig_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(2,0),C_DARK),("SPAN",(0,0),(2,0)),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
        ("BOX",(1,1),(1,5),1.5,C_BLUE),
        ("BACKGROUND",(1,1),(1,5),colors.HexColor("#f5f7ff")),
        ("PADDING",(0,0),(-1,-1),7),
    ]))
    story += [sig_t, Spacer(1, .4*cm),
              HRFlowable(width="100%", thickness=.5, color=colors.HexColor("#d1d5db")),
              Spacer(1, .15*cm),
              Paragraph("Losty Platform · Airport Lost & Found", SFTR),
              Paragraph(f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                        f"  ·  Act: ACT-{claim.l_number}  ·  Staff: {staff_name}", SFTR)]
    doc.build(story)
    raw = buf.getvalue()
    with open(fname_disk, "wb") as f:
        f.write(raw)
    return raw


def generate_disposal_act(found, staff_name) -> bytes:
    buf = io.BytesIO()
    fname_disk = f"acts/DisposalAct_{found.f_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = [
        Paragraph("✈  LOSTY PLATFORM", SH1),
        Paragraph("DISPOSAL ACT — EXPIRED STORAGE", SH2),
        HRFlowable(width="100%", thickness=2, color=C_RED, spaceAfter=6),
        Paragraph(f"DISPOSAL ACT &nbsp;|&nbsp; <b>DISP-{found.f_number}</b>"
                  f" &nbsp;|&nbsp; Date: <b>{datetime.now().strftime('%d %B %Y')}</b>", SSUB),
        Spacer(1, .4*cm),
        _sec_table("ITEM DETAILS", [
            ("Item ID", found.f_number),
            ("Description", (found.description or "")[:120]),
            ("Location Found", found.location_found or "—"),
            ("Finder", found.finder_name or "—"),
            ("Flight Number", found.flight_number or "—"),
            ("Date Registered", found.created_at.strftime("%d %B %Y %H:%M")),
            ("Status", "DISPOSED — Expired Storage"),
        ], C_RED),
        Spacer(1, .5*cm),
        Paragraph("This item's storage period has expired. In accordance with "
                  "airport regulations, the item has been processed for disposal.", SWRN),
        Spacer(1, .5*cm),
    ]
    sig_data = [
        [Paragraph("AUTHORIZED BY", ps("sh", fontName="Helvetica-Bold", fontSize=9,
                      textColor=colors.white, alignment=TA_CENTER)), ""],
        [Paragraph("STAFF MEMBER", SIGB), Paragraph("SUPERVISOR", SIGB)],
        [Paragraph("\n\n\n", SSIG), Paragraph("\n\n\n", SSIG)],
        [Paragraph(f"Name: {staff_name}", SSIG), Paragraph("Name: _______________", SSIG)],
        [Paragraph("Signature: _______________", SSIG),
         Paragraph("Signature: _______________", SSIG)],
    ]
    sig_t = Table(sig_data, colWidths=[8.4*cm, 8.4*cm])
    sig_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(1,0),C_RED),("SPAN",(0,0),(1,0)),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
        ("PADDING",(0,0),(-1,-1),7),
    ]))
    story += [sig_t, Spacer(1, .3*cm),
              Paragraph(f"Losty Platform · Disposal Act · {datetime.now().strftime('%d.%m.%Y %H:%M')}", SFTR)]
    doc.build(story)
    raw = buf.getvalue()
    with open(fname_disk, "wb") as f:
        f.write(raw)
    return raw


def generate_report_pdf(fi_list, lc_list, period_label, staff_name, rtype) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm)
    period_str = rtype.upper()
    story = [
        Paragraph("✈  LOSTY PLATFORM", SH1),
        Paragraph("OPERATIONAL REPORT", SH2),
        HRFlowable(width="100%", thickness=2, color=C_NAVY, spaceAfter=5),
        Paragraph(f"{period_str} REPORT &nbsp;|&nbsp; Period: <b>{period_label}</b>"
                  f" &nbsp;|&nbsp; By: <b>{staff_name}</b>"
                  f" &nbsp;|&nbsp; {datetime.now().strftime('%d %B %Y %H:%M')}", SSUB),
        Spacer(1, .4*cm),
    ]
    BIG = ps("big", fontName="Helvetica-Bold", fontSize=20, textColor=C_BLUE, alignment=TA_CENTER)
    summ = [
        [Paragraph("SUMMARY", ps("sh2", fontName="Helvetica-Bold", fontSize=9,
                      textColor=colors.white, alignment=TA_CENTER)), "", "", ""],
        [Paragraph("Found Items", SIGB), Paragraph("Lost Claims", SIGB),
         Paragraph("Matched", SIGB), Paragraph("Returned", SIGB)],
        [Paragraph(str(len(fi_list)), BIG), Paragraph(str(len(lc_list)), BIG),
         Paragraph(str(sum(1 for c in lc_list if c.status == "Matched")), BIG),
         Paragraph(str(sum(1 for c in lc_list if c.status == "Returned")), BIG)],
    ]
    st_ = Table(summ, colWidths=[4.1*cm]*4)
    st_.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(3,0),C_NAVY),("SPAN",(0,0),(3,0)),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_LTBL,colors.white]),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
        ("PADDING",(0,0),(-1,-1),8),
    ]))
    story += [st_, Spacer(1, .5*cm)]

    story += [Paragraph("FOUND ITEMS", SBLD), Spacer(1, .15*cm)]
    if fi_list:
        fhdr = [[Paragraph(h, SIGB) for h in ["ID","Description","Location","Status","Date"]]]
        frows = [[Paragraph(fi.f_number, SNM),
                  Paragraph((fi.description or "")[:60], SNM),
                  Paragraph(fi.location_found or "—", SNM),
                  Paragraph(fi.status.upper(), SNM),
                  Paragraph(fi.created_at.strftime("%d %b %Y"), SNM)] for fi in fi_list]
        ft = Table(fhdr+frows, colWidths=[2.0*cm,6.5*cm,3.5*cm,2.5*cm,2.5*cm])
        ft.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),C_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,C_LTBL]),
            ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
            ("PADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(ft)
    else:
        story.append(Paragraph("No found items in this period.", SNM))
    story.append(Spacer(1, .5*cm))

    story += [Paragraph("LOST CLAIMS (No Financial Data)", SBLD), Spacer(1, .15*cm)]
    if lc_list:
        lhdr = [[Paragraph(h, SIGB) for h in ["ID","Passenger","Description","Status","Date"]]]
        lrows = [[Paragraph(lc.l_number, SNM), Paragraph(lc.passenger_name, SNM),
                  Paragraph((lc.description or "")[:50], SNM),
                  Paragraph(lc.status.upper(), SNM),
                  Paragraph(lc.created_at.strftime("%d %b %Y"), SNM)] for lc in lc_list]
        lt = Table(lhdr+lrows, colWidths=[2.2*cm,3.5*cm,5.5*cm,2.5*cm,2.8*cm])
        lt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),C_DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,C_LTBL]),
            ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d1d5db")),
            ("PADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(lt)
    else:
        story.append(Paragraph("No lost claims in this period.", SNM))

    story += [Spacer(1, .4*cm),
              HRFlowable(width="100%", thickness=.5, color=colors.HexColor("#d1d5db")),
              Paragraph(f"Losty Platform · {period_str} Report · {period_label}", SFTR),
              Paragraph(f"By: {staff_name} · {datetime.now().strftime('%d.%m.%Y %H:%M')} · INTERNAL", SFTR)]
    doc.build(story)
    return buf.getvalue()

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
    cols = st.columns(len(metrics))
    for col,(val,lbl,icon) in zip(cols,metrics):
        col.markdown(f'<div class="metric-box"><div class="val">{icon} {val}</div>'
                     f'<div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)


# ── SESSION STATE ────────────────────────────────────────────────────────────
_DEFS = {"logged_in":False,"user_role":None,"username":None,
         "user_id":None,"fio":None,"page":"passenger","pdf_cache":{}}
for k,v in _DEFS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Losty Platform | Airport Lost & Found",
                   page_icon="✈️", layout="wide", initial_sidebar_state="expanded")
st.markdown(PAGE_CSS, unsafe_allow_html=True)

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><h2>✈️ Losty Platform</h2><p>Airport Lost &amp; Found</p></div>', unsafe_allow_html=True)
    
    st.markdown("#### 🗺️ Navigation")
    
    def nav_btn(label, page, roles=None):
        if roles and (not st.session_state.logged_in or st.session_state.user_role not in roles):
            return
        # Если кнопка активна — она синяя (primary)
        b_type = "primary" if st.session_state.page == page else "secondary"
        if st.button(label, use_container_width=True, type=b_type):
            st.session_state.page = page
            st.rerun()

    nav_btn("💼 Passenger Hub", "passenger")
    nav_btn("🏛️ Staff Portal", "staff", ["staff", "super_admin", "admin"])
    nav_btn("👑 Super-Admin", "admin", ["super_admin", "admin"])
    
    st.markdown("---")

    # Проверка: если НЕ залогинен — показываем форму входа
    if not st.session_state.logged_in:
        st.markdown("#### 🔐 Staff / Admin Login")
        with st.form("login_form", clear_on_submit=True):
            uname = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                s = Session()
                user = s.query(User).filter_by(username=uname, password_hash=_hash(pwd)).first()
                s.close()
                
                if user:
                    st.session_state.update({
                        "logged_in": True,
                        "user_role": user.role,
                        "username": user.username,
                        "user_id": user.id,
                        "fio": user.fio
                    })
                    audit("LOGIN", f"{user.username} ({user.role})")
                    
                    # АВТО-ПЕРЕХОД: направляем в нужный раздел сразу
                    if user.role in ['admin', 'super_admin']:
                        st.session_state.page = "admin"
                    else:
                        st.session_state.page = "staff"
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    
    # Если залогинен — показываем профиль и кнопку выхода
    else:
        st.markdown(f"👤 **{st.session_state.fio}**")
        r_label = "🛡️ Admin" if st.session_state.user_role in ['admin', 'super_admin'] else "🏛️ Staff"
        st.markdown(f"`{r_label}`")
        
        if st.button("🚪 Logout", use_container_width=True):
            audit("LOGOUT", st.session_state.username)
            # Сброс сессии
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.page = "passenger"
            st.rerun()

    st.markdown("---")
def page_passenger():
    header("🧳 Passenger Hub", "Lost something at the airport? File a claim and track your item.")
    tab_file, tab_track, tab_pay = st.tabs(["📝 File a Claim", "🔍 Track Claim", "💳 Payment"])

    with tab_file:
        st.markdown("### Submit a Lost Item Claim")
        st.info("Filing this claim initiates the search. Our team will contact you when a match is found.")
        with st.form("lost_claim_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### 🪪 Identity & Contact")
                pname    = st.text_input("Full Name *", placeholder="John Smith")
                passport = st.text_input("Passport Data *", placeholder="AA1234567")
                phone    = st.text_input("Phone Number", placeholder="+998 90 123 4567")
                email    = st.text_input("Email Address", placeholder="john@example.com")
            with c2:
                st.markdown("##### ✈️ Travel Information")
                arr_flight = st.text_input("Arrival Flight Number", placeholder="HY-201")
                arr_date   = st.text_input("Arrival Date", placeholder="2026-04-25")
                tran_flight= st.text_input("Transit Departure Flight", placeholder="HY-305")
                board_pass = st.text_input("Boarding Pass", placeholder="BP-12345")
                bag_tag    = st.text_input("Baggage Tag", placeholder="TAG-67890")

            st.markdown("---")
            st.markdown("##### 📦 Item Details")
            ic1, ic2 = st.columns(2)
            with ic1:
                loc_lost = st.text_input("Location Lost *", placeholder="Gate B12, Baggage Hall...")
                desc     = st.text_area("Item Description *", placeholder="Color, brand, marks...", height=100)
            with ic2:
                est_val  = st.number_input("Estimated Value ($)", min_value=0.0, step=10.0, value=0.0)
                img_up   = st.file_uploader("Item Photo (optional)", type=["jpg","jpeg","png","webp"])
                storage  = st.radio("Storage Choice *", ["service", "org"],
                    format_func=lambda x: "🏢 Service Storage ($5/day)" if x=="service"
                                          else "🏛️ Organisation Storage ($20/day)")

            st.markdown("---")
            st.markdown("#### 📋 5 Mandatory Rules — Accept All")
            rc1, rc2 = st.columns(2)
            with rc1:
                t1 = st.checkbox("1. I consent to personal data processing (Privacy)")
                t2 = st.checkbox("2. All information provided is accurate (Accuracy)")
                t3 = st.checkbox("3. I understand storage fees apply (Storage)")
            with rc2:
                t4 = st.checkbox("4. Unclaimed items will be disposed after 90 days (Disposal)")
                t5 = st.checkbox("5. I agree to service fees: $10 registration + commission on return (Fees)")

            submitted = st.form_submit_button("📤 Submit Lost Claim", use_container_width=True, type="primary")

        if submitted:
            errs = []
            if not all([pname, passport, loc_lost, desc]):
                errs.append("Please fill all required fields (*).")
            if not all([t1,t2,t3,t4,t5]):
                errs.append("Please accept all 5 mandatory rules.")
            if errs:
                for e in errs: st.error(e)
            else:
                s = Session()
                lnum = _next_l()
                s.add(LostClaim(
                    l_number=lnum, passenger_name=pname, passport_data=passport,
                    phone=phone, email=email, arrival_flight=arr_flight,
                    arrival_date=arr_date, transit_flight=tran_flight,
                    boarding_pass=board_pass, baggage_tag=bag_tag,
                    location_lost=loc_lost, description=desc,
                    estimated_value=est_val, storage_choice=storage,
                    image_path=_save_upload(img_up, "claim") if img_up else None,
                    rules_accepted=True))
                s.commit(); s.close()
                st.balloons()
                st.success("✅ Claim submitted!")
                st.markdown(f"""
                <div class="info-card">
                  <h3 style="margin:0;color:#0d1b4b;">Claim ID:
                    <code style="font-size:1.3rem;">{lnum}</code></h3>
                  <p style="margin:.5rem 0 0;color:#374151;">
                    Save this ID to track your claim. You will be contacted on match.</p>
                </div>""", unsafe_allow_html=True)

    with tab_track:
        st.markdown("### 🔍 Track Your Claim")
        c1, c2 = st.columns(2)
        with c1: search_id = st.text_input("Claim ID", placeholder="L-2026-0001").upper().strip()
        with c2: search_ph = st.text_input("Or Phone Number", placeholder="+998...").strip()
        if st.button("🔎 Search", type="primary", use_container_width=True):
            if not search_id and not search_ph:
                st.warning("Enter Claim ID or Phone Number.")
            else:
                s = Session()
                q = s.query(LostClaim)
                if search_id: q = q.filter(LostClaim.l_number == search_id)
                if search_ph: q = q.filter(LostClaim.phone.contains(search_ph))
                results = q.all()
                if results:
                    for cl in results:
                        co = {"Searching":("#fff7ed","#c2410c"),"Matched":("#f0fdf4","#15803d"),
                              "Returned":("#eff6ff","#1d4ed8"),"Disposed":("#fef2f2","#991b1b")}
                        bg, fg = co.get(cl.status, ("#fff","#000"))
                        ic = {"Searching":"⏳","Matched":"🔗","Returned":"🎉","Disposed":"🗑️"}
                        st.markdown(f"""
                        <div style="background:{bg};border-radius:12px;padding:1.3rem 1.7rem;
                                    border-left:5px solid {fg};margin-top:1rem;">
                          <h3 style="color:{fg};margin:0;">{ic.get(cl.status,'•')} {cl.l_number}</h3>
                          <table style="margin-top:.7rem;width:100%;font-size:.88rem;">
                            <tr><td style="padding:.28rem;color:#6b7280;width:160px;"><b>Passenger</b></td>
                                <td>{cl.passenger_name}</td></tr>
                            <tr><td style="padding:.28rem;color:#6b7280;"><b>Status</b></td>
                                <td><b style="color:{fg};">{cl.status.upper()}</b></td></tr>
                            <tr><td style="padding:.28rem;color:#6b7280;"><b>Description</b></td>
                                <td>{(cl.description or "")[:90]}</td></tr>
                            <tr><td style="padding:.28rem;color:#6b7280;"><b>Filed</b></td>
                                <td>{cl.created_at.strftime("%d %B %Y, %H:%M")}</td></tr>
                          </table>
                        </div>""", unsafe_allow_html=True)
                        if cl.status == "Matched":
                            st.success("🎉 Your item has been found! We will contact you soon.")
                        elif cl.status == "Returned":
                            st.success("✅ Item returned. Thank you for using Losty!")
                else:
                    st.error("No claims found.")
                s.close()

    with tab_pay:
        st.markdown("### 💳 Payment Portal (Simulated)")
        st.info("Enter your Claim ID to view and process payments.")
        pay_id = st.text_input("Claim ID for Payment", placeholder="L-2026-0001", key="pay_claim_id").upper().strip()
        if pay_id:
            s = Session()
            cl = s.query(LostClaim).filter(LostClaim.l_number == pay_id).first()
            if cl:
                st.markdown(f"""
                <div class="info-card">
                  <b>{cl.l_number}</b> — {cl.passenger_name}<br>
                  Status: <b>{cl.status}</b>
                </div>""", unsafe_allow_html=True)
                st.markdown("---")
                pc1, pc2 = st.columns(2)
                with pc1:
                    st.markdown("""<div class="pay-card">
                      <h4>Registration Fee: $10.00</h4>
                      <p style="font-size:.85rem;opacity:.8;">One-time claim registration fee</p>
                    </div>""", unsafe_allow_html=True)
                    if cl.fee_paid:
                        st.success("✅ Registration Fee PAID")
                    else:
                        st.markdown("##### Payment Method")
                        pay_method = st.selectbox("Select", ["Visa","Mastercard","Payoneer"], key="pm1")
                        card_num = st.text_input("Card Number", placeholder="4111 1111 1111 1111", key="cn1")
                        if st.button("💳 Pay $10 Registration Fee", type="primary", key="pay_fee_btn"):
                            cl.fee_paid = True
                            s.commit()
                            audit("PAYMENT", f"Fee $10 paid for {cl.l_number} via {pay_method}")
                            st.success("✅ Payment processed!")
                            st.rerun()
                with pc2:
                    if cl.status in ["Matched","Returned"]:
                        comm = 20 + (cl.estimated_value * 0.1)
                        st.markdown(f"""<div class="pay-card">
                          <h4>Commission: ${comm:.2f}</h4>
                          <p style="font-size:.85rem;opacity:.8;">$20 base + 10% of ${cl.estimated_value:.2f} value</p>
                        </div>""", unsafe_allow_html=True)
                        if cl.commission_paid:
                            st.success("✅ Commission PAID")
                        else:
                            pay_m2 = st.selectbox("Method", ["Visa","Mastercard","Payoneer"], key="pm2")
                            card2  = st.text_input("Card Number", placeholder="5500 0000 0000 0004", key="cn2")
                            if st.button(f"💳 Pay ${comm:.2f} Commission", type="primary", key="pay_comm_btn"):
                                cl.commission_paid = True
                                cl.reward_amount = cl.estimated_value * 0.1
                                s.commit()
                                audit("PAYMENT", f"Commission ${comm:.2f} for {cl.l_number}")
                                st.success("✅ Commission paid!")
                                st.rerun()
                    else:
                        st.info("Commission payment available after item is matched.")
            else:
                st.error("Claim not found.")
            s.close()

def page_staff():
    if not st.session_state.logged_in or st.session_state.user_role not in ["staff","super_admin"]:
        st.error("🔒 Access denied."); return
    IS_STAFF = st.session_state.user_role == "staff"
    header("🏛️ Staff Portal", "Register · Search · Match · Acts · Reports")
    

    tab_reg, tab_search, tab_match, tab_acts, tab_report = st.tabs([
        "📦 Register Found","🔍 Search Claims","🔗 Match","📄 Acts","📊 Reports"])

    with tab_reg:
        st.markdown("### Register a New Found Item")
        with st.form("reg_found_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                f_desc = st.text_area("Description *", placeholder="Black Samsonite suitcase...", height=100)
                f_loc = st.text_input("Where Found *", placeholder="Gate B12, Baggage Hall...")
                f_finder = st.text_input("Finder Name", placeholder="Staff name or passenger")
                f_flight = st.text_input("Flight Number (optional)", placeholder="HY-201")
            with c2:
                st.markdown("##### 📷 Photos (up to 3)")
                f_img1 = st.file_uploader("Photo 1", type=["jpg","jpeg","png","webp"], key="fi1")
                f_img2 = st.file_uploader("Photo 2", type=["jpg","jpeg","png","webp"], key="fi2")
                f_img3 = st.file_uploader("Photo 3", type=["jpg","jpeg","png","webp"], key="fi3")
            if st.form_submit_button("📥 Register Found Item", use_container_width=True, type="primary"):
                if not f_desc or not f_loc:
                    st.error("Description and Location required.")
                else:
                    s = Session()
                    fnum = _next_f()
                    p1 = _save_upload(f_img1,"found") if f_img1 else None
                    p2 = _save_upload(f_img2,"found") if f_img2 else None
                    p3 = _save_upload(f_img3,"found") if f_img3 else None
                    s.add(FoundItem(f_number=fnum, description=f_desc, location_found=f_loc,
                                    finder_name=f_finder, flight_number=f_flight,
                                    image_path1=p1, image_path2=p2, image_path3=p3,
                                    created_by_id=st.session_state.user_id))
                    s.commit(); s.close()
                    audit("REGISTER_FOUND", f"{fnum} at {f_loc}")
                    st.success(f"✅ Registered: **{fnum}**")

        st.markdown("---")
        st.markdown("#### All Found Items")
        s = Session()
        items = s.query(FoundItem).order_by(FoundItem.created_at.desc()).all()
        if items:
            rows = "".join(
                f"<tr><td>{i.f_number}</td><td>{(i.description or '')[:60]}</td>"
                f"<td>{i.location_found or '—'}</td><td>{pill(i.status)}</td>"
                f"<td>{i.created_at.strftime('%d %b %Y %H:%M')}</td></tr>" for i in items)
            st.markdown('<table class="data-table"><thead><tr>'
                '<th>ID</th><th>Description</th><th>Location</th><th>Status</th><th>Date</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        else:
            st.info("No found items yet.")
        s.close()

    with tab_search:
        st.markdown("### 🔍 Search Claims")
        sc1, sc2 = st.columns(2)
        with sc1: sid = st.text_input("Search by Claim ID", placeholder="L-2026-0001").upper().strip()
        with sc2: sph = st.text_input("Search by Phone", placeholder="+998...").strip()
        if st.button("🔎 Search", key="staff_search", type="primary"):
            s = Session()
            q = s.query(LostClaim)
            if sid: q = q.filter(LostClaim.l_number == sid)
            if sph: q = q.filter(LostClaim.phone.contains(sph))
            results = q.all()
            for cl in results:
                with st.expander(f"{cl.l_number} — {cl.passenger_name} — {cl.status}", expanded=True):
                    cc1, cc2 = st.columns(2)
                    cc1.markdown(f"**Name:** {cl.passenger_name}  \n**Passport:** {cl.passport_data}  \n"
                                 f"**Phone:** {cl.phone or '—'}  \n**Email:** {cl.email or '—'}")
                    cc2.markdown(f"**Flight:** {cl.arrival_flight or '—'}  \n"
                                 f"**Location Lost:** {cl.location_lost or '—'}  \n"
                                 f"**Description:** {(cl.description or '')[:80]}  \n"
                                 f"**Status:** {cl.status}")
                    if cl.image_path and os.path.exists(cl.image_path):
                        st.image(cl.image_path, caption="Passenger photo", width=300)
            if not results:
                st.warning("No claims found.")
            s.close()

    with tab_match:
        st.markdown("### Match Found Items with Claims")
        s = Session()
        eligible = s.query(LostClaim).filter(LostClaim.fee_paid==True, LostClaim.status=="Searching").order_by(LostClaim.created_at.desc()).all()
        avail = s.query(FoundItem).filter(FoundItem.status=="registered").order_by(FoundItem.created_at.desc()).all()
        s.close()
        if not eligible:
            st.info("No cleared claims for matching.")
        elif not avail:
            st.info("No unmatched found items.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🧳 Eligible Claims")
                copts = {f"{c.l_number} — {c.passenger_name}": c.id for c in eligible}
                sck = st.selectbox("Select Claim", list(copts.keys()))
                s = Session()
                cl = s.query(LostClaim).get(copts[sck])
                st.markdown(f'<div class="info-card" style="border-color:#15803d;">'
                    f'<b>{cl.l_number}</b> · {cl.passenger_name}<br>'
                    f'📍 Lost at: {cl.location_lost or "—"}<br>'
                    f'<i>"{(cl.description or "")[:100]}"</i></div>', unsafe_allow_html=True)
                if cl.image_path and os.path.exists(cl.image_path):
                    st.image(cl.image_path, caption="Passenger's photo", use_container_width=True)
                s.close()
            with c2:
                st.markdown("#### 📦 Found Items")
                fopts = {f"{f.f_number} — {(f.description or '')[:40]}": f.id for f in avail}
                sfk = st.selectbox("Select Found Item", list(fopts.keys()))
                s = Session()
                fi = s.query(FoundItem).get(fopts[sfk])
                st.markdown(f'<div class="info-card" style="border-color:#1d4ed8;">'
                    f'<b>{fi.f_number}</b><br>📍 {fi.location_found or "—"}<br>'
                    f'<i>"{(fi.description or "")[:100]}"</i></div>', unsafe_allow_html=True)
                for ip in [fi.image_path1, fi.image_path2, fi.image_path3]:
                    if ip and os.path.exists(ip):
                        st.image(ip, use_container_width=True)
                s.close()

            # AI Similarity
            s = Session()
            cl = s.query(LostClaim).get(copts[sck])
            fi = s.query(FoundItem).get(fopts[sfk])
            score = ai_similarity(cl.location_lost, fi.location_found, cl.description, fi.description)
            color = "#15803d" if score > 60 else "#c2410c" if score > 30 else "#991b1b"
            st.markdown(f'<div style="background:#f8fafc;border-radius:12px;padding:1rem;text-align:center;'
                f'margin:1rem 0;border:2px solid {color};">'
                f'<span style="font-size:2rem;font-weight:700;color:{color};">{score}%</span><br>'
                f'<span style="color:#6b7280;">AI Similarity Score</span></div>', unsafe_allow_html=True)
            s.close()

            if st.button("🤝 Create Match", use_container_width=True):
                s = Session()
                try:
                # 1. Сначала находим объекты в базе
                # (Убедись, что переменные selected_claim_id и selected_found_id определены выше в твоем коде)
                cl = s.query(Claim).get(selected_claim_id)
                fi = s.query(FoundItem).get(selected_found_id)

                if cl and fi:
                    # 2. КРИТИЧЕСКИЙ МОМЕНТ: сохраняем номера в обычные переменные
                    claim_no = cl.l_number
                    found_no = fi.f_number

                    # 3. Обновляем статусы (Теперь с правильным отступом!)
                    cl.status = "Matched"
                    cl.matched_with = fi.id
                    fi.status = "Matched"
                    fi.matched_with = cl.id

                    # 4. Записываем в аудит
                    audit("MATCH", f"{claim_no} ↔ {found_no}")

                    s.commit()
                    st.success(f"✅ Match Created: {claim_no}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Could not find Claim or Found Item in database.")
                except Exception as e:
                s.rollback()
                st.error(f"❌ Database Error: {e}")
                finally:
                # 5. Закрываем сессию только в самом конце
                s.close()

    with tab_acts:
        st.markdown("### 📄 Generate Acts")
        act_type = st.radio("Act Type", ["Return Act","Disposal Act"], horizontal=True)
        s = Session()
        if act_type == "Return Act":
            matched = s.query(LostClaim).filter(LostClaim.status=="Matched").all()
            if not matched:
                st.info("No matched claims.")
            for cl in matched:
                fi = s.query(FoundItem).get(cl.found_item_id) if cl.found_item_id else None
                if not fi: continue
                key_pdf = f"pdf_{cl.id}"
                with st.expander(f"📄 {cl.l_number} · {cl.passenger_name} ↔ {fi.f_number}", expanded=True):
                    cc1, cc2 = st.columns(2)
                    cc1.markdown(f"**Claim:** {cl.l_number}  \n**Passenger:** {cl.passenger_name}  \n"
                                 f"**Passport:** {cl.passport_data or '—'}  \n**Filed:** {cl.created_at.strftime('%d %b %Y')}")
                    cc2.markdown(f"**Found:** {fi.f_number}  \n**Location:** {fi.location_found or '—'}  \n"
                                 f"**Finder:** {fi.finder_name or '—'}  \n**Registered:** {fi.created_at.strftime('%d %b %Y')}")
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("📄 Generate PDF", key=f"gpdf_{cl.id}", use_container_width=True):
                            raw = generate_return_act(cl, fi, st.session_state.fio or "Staff")
                            st.session_state["pdf_cache"][key_pdf] = raw
                            audit("PDF_RETURN", f"Act for {cl.l_number}")
                            st.success("✅ PDF ready!")
                        if key_pdf in st.session_state.get("pdf_cache",{}):
                            st.download_button("⬇️ Download", data=st.session_state["pdf_cache"][key_pdf],
                                file_name=f"ReturnAct_{cl.l_number}.pdf", mime="application/pdf",
                                key=f"dl_{cl.id}", use_container_width=True)
                    with bc2:
                        if st.button("✅ Mark Returned", key=f"ret_{cl.id}", use_container_width=True):
                            cl.status="Returned"; fi.status="returned"
                            s.commit(); audit("RETURN", cl.l_number)
                            st.success("Returned!"); st.rerun()
        else:
            disposable = s.query(FoundItem).filter(FoundItem.status.in_(["registered","identified"])).all()
            if not disposable:
                st.info("No items for disposal.")
            for fi in disposable:
                key_dp = f"disp_pdf_{fi.id}"
                with st.expander(f"🗑️ {fi.f_number} · {(fi.description or '')[:50]}", expanded=False):
                    st.markdown(f"**Location:** {fi.location_found}  \n**Registered:** {fi.created_at.strftime('%d %b %Y')}")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("📄 Disposal Act PDF", key=f"gdis_{fi.id}", use_container_width=True):
                            raw = generate_disposal_act(fi, st.session_state.fio or "Staff")
                            st.session_state["pdf_cache"][key_dp] = raw
                            audit("PDF_DISPOSAL", fi.f_number)
                            st.success("✅ PDF ready!")
                        if key_dp in st.session_state.get("pdf_cache",{}):
                            st.download_button("⬇️ Download", data=st.session_state["pdf_cache"][key_dp],
                                file_name=f"DisposalAct_{fi.f_number}.pdf", mime="application/pdf",
                                key=f"dld_{fi.id}", use_container_width=True)
                    with dc2:
                        if st.button("🗑️ Mark Disposed", key=f"mkdisp_{fi.id}", use_container_width=True):
                            fi.status = "disposed"
                            if fi.matched_claim_id:
                                mc = s.query(LostClaim).get(fi.matched_claim_id)
                                if mc: mc.status = "Disposed"
                            s.commit(); audit("DISPOSE", fi.f_number)
                            st.warning("Disposed."); st.rerun()
        s.close()

    with tab_report:
        st.markdown("### 📊 Operational Reports")
        rtype = st.radio("Period", ["Daily","Monthly","Quarterly"], horizontal=True)
        s = Session()
        if rtype == "Daily":
            rd = st.date_input("Date", value=date.today())
            ds = datetime.combine(rd, datetime.min.time())
            de = ds + timedelta(days=1)
            fi_q = s.query(FoundItem).filter(FoundItem.created_at>=ds, FoundItem.created_at<de)
            lc_q = s.query(LostClaim).filter(LostClaim.created_at>=ds, LostClaim.created_at<de)
            plabel = rd.strftime("%d %B %Y")
        elif rtype == "Monthly":
            mc, yc = st.columns(2)
            with mc: rm = st.selectbox("Month", range(1,13), index=datetime.now().month-1,
                          format_func=lambda m: datetime(2000,m,1).strftime("%B"))
            with yc: ry = st.selectbox("Year", range(2024, datetime.now().year+1))
            fi_q = s.query(FoundItem).filter(func.strftime("%Y",FoundItem.created_at)==str(ry),
                          func.strftime("%m",FoundItem.created_at)==f"{rm:02d}")
            lc_q = s.query(LostClaim).filter(func.strftime("%Y",LostClaim.created_at)==str(ry),
                          func.strftime("%m",LostClaim.created_at)==f"{rm:02d}")
            plabel = datetime(ry,rm,1).strftime("%B %Y")
        else:
            qsel = st.selectbox("Quarter", ["Q1 (Jan-Mar)","Q2 (Apr-Jun)","Q3 (Jul-Sep)","Q4 (Oct-Dec)"])
            qy = st.selectbox("Year", range(2024, datetime.now().year+1), key="qy")
            qn = int(qsel[1])
            sm = (qn-1)*3+1
            ds = datetime(qy, sm, 1)
            de = datetime(qy, sm+3, 1) if sm+3 <= 12 else datetime(qy+1, 1, 1)
            fi_q = s.query(FoundItem).filter(FoundItem.created_at>=ds, FoundItem.created_at<de)
            lc_q = s.query(LostClaim).filter(LostClaim.created_at>=ds, LostClaim.created_at<de)
            plabel = f"{qsel} {qy}"

        fi_list = fi_q.order_by(FoundItem.created_at).all()
        lc_list = lc_q.order_by(LostClaim.created_at).all()
        s.close()
        metric_strip([
            (str(len(fi_list)), "Found Items", "📦"),
            (str(len(lc_list)), "Lost Claims", "🧳"),
            (str(sum(1 for c in lc_list if c.status=="Matched")), "Matched", "🔗"),
            (str(sum(1 for c in lc_list if c.status=="Returned")), "Returned", "🎉"),
        ])
        rpt_key = f"rpt_{rtype}_{plabel}"
        if st.button("📊 Generate PDF Report", type="primary", use_container_width=True):
            if fi_list or lc_list:
                raw = generate_report_pdf(fi_list, lc_list, plabel,
                                          st.session_state.fio or "Staff", rtype.lower())
                st.session_state["pdf_cache"][rpt_key] = raw
                st.success("✅ Report ready!")
            else:
                st.warning("No data for this period.")
        if rpt_key in st.session_state.get("pdf_cache",{}):
            st.download_button("⬇️ Download Report", data=st.session_state["pdf_cache"][rpt_key],
                file_name=f"Report_{plabel.replace(' ','_')}.pdf", mime="application/pdf",
                key=f"dl_{rpt_key}", use_container_width=True)


def page_admin():
    if not st.session_state.logged_in or st.session_state.user_role != "super_admin":
        st.error("🔒 Super-Admin only."); return
    header("👑 Super-Admin Panel", "Financials · Payments · Audit · Users · Reports")
    s = Session()
    total = s.query(LostClaim).count()
    fee_n = s.query(LostClaim).filter(LostClaim.fee_paid==True).count()
    mat_n = s.query(LostClaim).filter(LostClaim.status=="Matched").count()
    ret_n = s.query(LostClaim).filter(LostClaim.status=="Returned").count()
    com_n = s.query(LostClaim).filter(LostClaim.commission_paid==True).count()
    metric_strip([
        (str(total), "Total Claims", "📋"),
        (str(fee_n), f"Fee Paid (${fee_n*10})", "💰"),
        (str(mat_n), "Matched", "🔗"),
        (str(ret_n), "Returned", "🎉"),
        (str(com_n), f"Commissions (${com_n*20}+)", "💵"),
    ])

    tab_pay, tab_all, tab_audit, tab_users, tab_rpt = st.tabs([
        "💳 Payments","📊 All Claims","📜 Audit Log","👥 Users","🖨️ Reports"])

    with tab_pay:
        st.markdown("### Payment Management")
        filt = st.selectbox("Filter", ["All","Searching","Matched","Returned","Disposed"])
        q = s.query(LostClaim)
        if filt != "All": q = q.filter(LostClaim.status==filt)
        for cl in q.order_by(LostClaim.created_at.desc()).all():
            c1,c2,c3,c4 = st.columns([3,2,2.5,2])
            c1.markdown(f"**{cl.l_number}** {pill(cl.status)}<br>{cl.passenger_name}<br>"
                f"<small>📧 {cl.email or '—'} · 📅 {cl.created_at.strftime('%d %b %Y')}</small>",
                unsafe_allow_html=True)
            c2.markdown(f"**Storage:** {'Service' if cl.storage_choice=='service' else 'Org'}<br>"
                f"**Passport:** {cl.passport_data or '—'}<br>**Value:** ${cl.estimated_value:.0f}",
                unsafe_allow_html=True)
            with c3:
                icon = "✅" if cl.fee_paid else "❌"
                st.markdown(f"**Reg. Fee ($10):** {icon}")
                if not cl.fee_paid:
                    if st.button("💳 Mark $10 Paid", key=f"fee_{cl.id}", type="primary"):
                        cl.fee_paid=True; s.commit()
                        audit("ADMIN_FEE", f"$10 for {cl.l_number}"); st.rerun()
                else:
                    if st.button("↩️ Reverse Fee", key=f"unfee_{cl.id}"):
                        cl.fee_paid=False; s.commit(); st.rerun()
            with c4:
                if cl.status in ["Matched","Returned"]:
                    due = 20 + (cl.estimated_value * 0.1)
                    icon = "✅" if cl.commission_paid else "❌"
                    st.markdown(f"**Commission:** {icon} ${due:.0f}")
                    if not cl.commission_paid:
                        if st.button(f"💳 ${due:.0f}", key=f"comm_{cl.id}", type="primary"):
                            cl.commission_paid=True; cl.reward_amount=cl.estimated_value*0.1
                            s.commit(); audit("ADMIN_COMM", f"${due:.0f} for {cl.l_number}")
                            st.rerun()
                    else:
                        if st.button("↩️ Reverse", key=f"ucomm_{cl.id}"):
                            cl.commission_paid=False; s.commit(); st.rerun()
            st.markdown("<hr style='margin:.3rem 0;border-color:#e5e7eb;'>", unsafe_allow_html=True)

    with tab_all:
        import pandas as pd
        st.markdown("### Full Claims Database")
        rows = []
        for cl in s.query(LostClaim).order_by(LostClaim.created_at.desc()).all():
            rows.append({"Claim ID":cl.l_number, "Passenger":cl.passenger_name,
                "Passport":cl.passport_data or "—", "Phone":cl.phone or "—",
                "Flight":cl.arrival_flight or "—", "Location Lost":cl.location_lost or "—",
                "Value":f"${cl.estimated_value:.0f}", "Status":cl.status,
                "Fee($10)":"✅" if cl.fee_paid else "❌",
                "Commission":"✅" if cl.commission_paid else "❌",
                "Storage":cl.storage_choice, "Filed":cl.created_at.strftime("%d %b %Y")})
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=420)
            st.download_button("⬇️ CSV", data=df.to_csv(index=False).encode(),
                file_name="losty_claims.csv", mime="text/csv")
        else:
            st.info("No claims.")

    with tab_audit:
        st.markdown("### 📜 Audit Log")
        logs = s.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
        if logs:
            rows = "".join(
                f"<tr><td>{l.created_at.strftime('%d %b %Y %H:%M')}</td>"
                f"<td><b>{l.user_fio or '—'}</b></td>"
                f"<td>{l.action}</td><td>{l.detail or '—'}</td></tr>" for l in logs)
            st.markdown('<table class="data-table"><thead><tr>'
                '<th>Time</th><th>Staff FIO</th><th>Action</th><th>Detail</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        else:
            st.info("No audit entries.")

    with tab_users:
        import pandas as pd
        st.markdown("### 👥 User Management")
        users = s.query(User).all()
        st.dataframe(pd.DataFrame([{
            "ID":u.id, "Username":u.username, "Role":u.role,
            "FIO":u.fio or "—",
            "Created":u.created_at.strftime("%d %b %Y") if u.created_at else "—",
        } for u in users]), use_container_width=True, hide_index=True)
        st.markdown("#### ➕ Create Staff Account")
        with st.form("new_user_form", clear_on_submit=True):
            nc1, nc2 = st.columns(2)
            with nc1:
                nu_fio = st.text_input("Full Name (FIO)")
                nu_uname = st.text_input("Username")
            with nc2:
                nu_pw = st.text_input("Password", type="password")
                nu_role = st.selectbox("Role", ["staff","super_admin"])
            if st.form_submit_button("➕ Create User", type="primary"):
                if not all([nu_fio, nu_uname, nu_pw]):
                    st.error("All fields required.")
                elif s.query(User).filter_by(username=nu_uname).first():
                    st.error("Username exists.")
                else:
                    s.add(User(fio=nu_fio, username=nu_uname,
                               password_hash=_hash(nu_pw), role=nu_role))
                    s.commit()
                    audit("CREATE_USER", f"{nu_uname} ({nu_role})")
                    st.success(f"Created '{nu_uname}'!"); st.rerun()

    with tab_rpt:
        st.markdown("### 🖨️ Admin Reports (with Financial Data)")
        rtype = st.radio("Period", ["Daily","Monthly","Quarterly"], horizontal=True, key="arpt")
        if rtype == "Daily":
            rd = st.date_input("Date", value=date.today(), key="ard")
            ds = datetime.combine(rd, datetime.min.time())
            de = ds + timedelta(days=1)
            fi_q = s.query(FoundItem).filter(FoundItem.created_at>=ds, FoundItem.created_at<de)
            lc_q = s.query(LostClaim).filter(LostClaim.created_at>=ds, LostClaim.created_at<de)
            plabel = rd.strftime("%d %B %Y")
        elif rtype == "Monthly":
            mc2, yc2 = st.columns(2)
            with mc2: rm = st.selectbox("Month", range(1,13), index=datetime.now().month-1,
                          format_func=lambda m: datetime(2000,m,1).strftime("%B"), key="arm")
            with yc2: ry = st.selectbox("Year", range(2024, datetime.now().year+1), key="ary")
            fi_q = s.query(FoundItem).filter(func.strftime("%Y",FoundItem.created_at)==str(ry),
                          func.strftime("%m",FoundItem.created_at)==f"{rm:02d}")
            lc_q = s.query(LostClaim).filter(func.strftime("%Y",LostClaim.created_at)==str(ry),
                          func.strftime("%m",LostClaim.created_at)==f"{rm:02d}")
            plabel = datetime(ry,rm,1).strftime("%B %Y")
        else:
            qsel = st.selectbox("Quarter", ["Q1","Q2","Q3","Q4"], key="arq")
            qy = st.selectbox("Year", range(2024, datetime.now().year+1), key="arqy")
            qn = int(qsel[1])
            sm = (qn-1)*3+1
            ds = datetime(qy, sm, 1)
            de = datetime(qy, sm+3, 1) if sm+3<=12 else datetime(qy+1,1,1)
            fi_q = s.query(FoundItem).filter(FoundItem.created_at>=ds, FoundItem.created_at<de)
            lc_q = s.query(LostClaim).filter(LostClaim.created_at>=ds, LostClaim.created_at<de)
            plabel = f"{qsel} {qy}"
        fi_list = fi_q.all(); lc_list = lc_q.all()
        rpt_key = f"admin_rpt_{rtype}_{plabel}"
        if st.button("📊 Generate Admin PDF", type="primary", key="admin_rpt_btn"):
            if fi_list or lc_list:
                raw = generate_report_pdf(fi_list, lc_list, plabel, st.session_state.fio or "Admin", rtype.lower())
                st.session_state["pdf_cache"][rpt_key] = raw
                st.success("✅ Ready!")
        if rpt_key in st.session_state.get("pdf_cache",{}):
            st.download_button("⬇️ Download", data=st.session_state["pdf_cache"][rpt_key],
                file_name=f"AdminReport_{plabel.replace(' ','_')}.pdf", mime="application/pdf",
                key=f"dl_{rpt_key}")
    s.close()


# ── ROUTER ───────────────────────────────────────────────────────────────────
if st.session_state.page == "passenger":
    page_passenger()
elif st.session_state.page == "staff":
    page_staff()
elif st.session_state.page == "admin":
    page_admin()
