# Staff portal page function
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

            if st.button("🔗 Create Match", type="primary", use_container_width=True):
                s = Session()
                cl = s.query(LostClaim).get(copts[sck])
                fi = s.query(FoundItem).get(fopts[sfk])
                cl.found_item_id = fi.id; cl.status = "Matched"
                fi.status = "identified"; fi.matched_claim_id = cl.id
                s.commit(); s.close()
                audit("MATCH", f"{cl.l_number} ↔ {fi.f_number}")
                st.success("✅ Matched!"); st.rerun()

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
