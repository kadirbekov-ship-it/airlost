# Super-Admin page + router
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
