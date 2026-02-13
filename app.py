import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. প্রিমিয়াম UI কনফিগারেশন ও স্টাইলিং ---
st.set_page_config(
    page_title="SpamGuard Pro AI - Professional Edition",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-title { font-size: 45px; font-weight: 800; color: #1a73e8; text-align: center; margin-bottom: 5px; }
    .sub-title { font-size: 18px; color: #5f6368; text-align: center; margin-bottom: 35px; }
    .stButton>button { width: 100%; border-radius: 30px; font-weight: bold; height: 3.5em; transition: 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(26,115,232,0.2); }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট (User Persistence) ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. এআই ও স্মার্ট প্রোটেকশন লজিক ---
def smart_whitelist(subject, sender):
    """ভুল ডিটেকশন কমানোর জন্য সুরক্ষা স্তর"""
    safe_domains = ["google.com", "linkedin.com", "github.com", "hackerrank.com", "udemy.com", "coursera.org", ".edu", ".gov"]
    safe_words = ["security", "alert", "cloud", "action advised", "verification", "otp", "interview", "exam", "grade"]
    
    sender, subject = sender.lower(), subject.lower()
    for d in safe_domains:
        if d in sender: return True
    for w in safe_words:
        if w in subject: return True
    return False

@st.cache_resource
def load_assets():
    """এআই মডেল লোড"""
    try:
        return joblib.load('final_model.pkl'), joblib.load('final_vectorizer.pkl')
    except: return None, None

model, vectorizer = load_assets()

def connect_gmail(u, p):
    """জিমেইল কানেকশন"""
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com")
        m.login(u, p)
        return m
    except: return None

# --- ৪. সাইডবার কন্ট্রোল সেন্টার ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    st.title("SpamGuard Pro")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Access")
        u = st.text_input("Gmail Address")
        p = st.text_input("App Password", type="password")
        if st.button("🚀 Access Inbox"):
            if connect_gmail(u, p):
                st.session_state.logged_in, st.session_state.u, st.session_state.p = True, u, p
                st.rerun()
            else: st.error("❌ Invalid App Password!")
    else:
        st.success(f"Connected: {st.session_state.u}")
        new_f = st.selectbox("📂 Scan Folder", ["INBOX", "[Gmail]/Spam"])
        if new_f != st.session_state.current_folder:
            st.session_state.current_folder = new_f
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        st.session_state.limit = st.select_slider("Scan Depth", options=[10, 20, 50, 100], value=20)
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ SpamGuard Pro AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Advanced Email Security & Inbox Optimizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner(f"🔍 AI is scanning {st.session_state.current_folder}..."):
            mail = connect_gmail(st.session_state.u, st.session_state.p)
            if mail:
                mail.select(f'"{st.session_state.current_folder}"')
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-st.session_state.limit:]
                    data = []
                    for uid in reversed(uids):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subj = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sndr = msg.get("From", "")
                            
                            is_safe_by_rule = smart_whitelist(subj, sndr)
                            status, action_bool = "🟢 Safe", False
                            
                            if not is_safe_by_rule and model:
                                prob = model.predict_proba(vectorizer.transform([subj]))[0][1]
                                if prob > 0.45: status, action_bool = "🔴 Spam", True # স্প্যাম হলে অটো টিক
                            
                            data.append({"UID": uid.decode(), "Subject": subj, "Sender": sndr, "Verdict": status, "Action": action_bool})
                        except: continue
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    # ড্যাশবোর্ড মেট্রিক্স
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("✅ Verified Safe", len(df[df['Verdict']=='🟢 Safe']))
        c3.metric("🚨 Spam Detected", len(df[df['Verdict']=='🔴 Spam']))

        # স্মার্ট এডিটর টেবিল
        col_label = "📥 Recover" if st.session_state.current_folder == "[Gmail]/Spam" else "🚀 Clean"
        edited_df = st.data_editor(df, column_config={"UID": None, "Action": st.column_config.CheckboxColumn(col_label, default=False)}, hide_index=True, use_container_width=True)
        to_move = edited_df[edited_df['Action'] == True]

        # অ্যাকশন বাটন ইঞ্জিন
        btn_col1, btn_col2 = st.columns(2)
        move_label = "📥 Move to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "🚀 Move to Spam"
        
        if btn_col1.button(move_label, type="primary", disabled=len(to_move)==0):
            with st.spinner("Processing..."):
                try:
                    mail = connect_gmail(st.session_state.u, st.session_state.p)
                    source = st.session_state.current_folder
                    dest = "INBOX" if source == "[Gmail]/Spam" else "[Gmail]/Spam"
                    mail.select(f'"{source}"')
                    for uid in to_move['UID'].tolist():
                        mail.uid('COPY', uid.encode(), f'"{dest}"')
                        mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                    mail.expunge()
                    mail.logout()
                    st.balloons()
                    st.success(f"✨ Successfully moved {len(to_move)} items!")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except: st.error("Action Failed.")

        if st.session_state.current_folder == "[Gmail]/Spam":
            if btn_col2.button("🗑️ Wipe Permanently", type="secondary", disabled=len(to_move)==0):
                mail = connect_gmail(st.session_state.u, st.session_state.p)
                mail.select('"[Gmail]/Spam"')
                for uid in to_move['UID'].tolist():
                    mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                mail.expunge()
                mail.logout()
                st.success("🔥 Selected spam deleted forever!")
                time.sleep(1)
                st.session_state.emails_df = pd.DataFrame()
                st.rerun()
else:
    st.info("👋 Welcome! Protect your inbox with AI-driven security.")
