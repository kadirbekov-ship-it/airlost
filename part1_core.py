
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
