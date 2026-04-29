# part3_passenger.py — Passenger Hub page

PASSENGER_PAGE = '''
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
'''
