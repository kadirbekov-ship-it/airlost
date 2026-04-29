"""Assemble app.py from parts."""
import re

# Read parts
with open("part1_core.py") as f:
    core = f.read()
with open("part2_pages.py") as f:
    css = f.read()
    css = css.replace("    import streamlit as st\n", "")
with open("part3_passenger.py") as f:
    p3 = f.read()
# Extract function body from PASSENGER_PAGE string
lines = p3.split("\n")
func_lines = []
inside = False
for line in lines:
    if "PASSENGER_PAGE = '''" in line:
        inside = True
        continue
    if line.strip() == "'''":
        inside = False
        continue
    if inside:
        func_lines.append(line)
passenger = "\n".join(func_lines)

with open("part4_staff.py") as f:
    staff = f.read()
    staff = "\n".join(l for l in staff.split("\n") if not l.startswith("# Staff portal"))
with open("part5_admin.py") as f:
    admin = f.read()
    admin = "\n".join(l for l in admin.split("\n") if not l.startswith("# Super-Admin"))

SIDEBAR = '''
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

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><h2>✈️ Losty Platform</h2><p>Airport Lost &amp; Found</p></div>', unsafe_allow_html=True)
    st.markdown("#### 🗺️ Navigation")
    def nav_btn(label, page, roles=None):
        if roles and (not st.session_state.logged_in or st.session_state.user_role not in roles):
            return
        if st.button(label, use_container_width=True,
                     type="primary" if st.session_state.page==page else "secondary"):
            st.session_state.page = page; st.rerun()
    nav_btn("🧳 Passenger Hub", "passenger")
    nav_btn("🏛️ Staff Portal", "staff", ["staff","super_admin"])
    nav_btn("👑 Super-Admin", "admin", ["super_admin"])
    st.markdown("---")
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
                    st.session_state.update({"logged_in":True,"user_role":user.role,
                        "username":user.username,"user_id":user.id,"fio":user.fio})
                    audit("LOGIN", f"{user.username} ({user.role})")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        labels = {"staff":"🏛️ Staff","super_admin":"👑 Super Admin"}
        st.markdown(f"**{st.session_state.fio}**")
        st.markdown(f"`{labels.get(st.session_state.user_role,'')}`")
        if st.button("🚪 Logout", use_container_width=True):
            audit("LOGOUT", st.session_state.username)
            for k in _DEFS: st.session_state[k] = _DEFS[k]
            st.session_state.page = "passenger"; st.rerun()
    st.markdown("---")
    st.markdown('<div style="font-size:.71rem;color:#888;text-align:center;line-height:1.75;"><b>Demo login</b><br>admin / admin123</div>', unsafe_allow_html=True)
'''

ROUTER = '''
# ── ROUTER ───────────────────────────────────────────────────────────────────
if st.session_state.page == "passenger":
    page_passenger()
elif st.session_state.page == "staff":
    page_staff()
elif st.session_state.page == "admin":
    page_admin()
'''

# Remove the leading comment line from part2
css_lines = css.split("\n")
css_clean = "\n".join(l for l in css_lines if not l.startswith("# part2"))

# Assemble
app = core + "\n" + css_clean + "\n" + SIDEBAR + "\n\n" + passenger + "\n\n" + staff + "\n\n" + admin + "\n" + ROUTER

with open("app.py", "w") as f:
    f.write(app)

print(f"app.py assembled: {len(app.split(chr(10)))} lines")
