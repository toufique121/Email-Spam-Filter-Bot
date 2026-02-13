import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও প্রিমিয়াম থিম ---
st.set_page_config(
    page_title="SpamGuard Pro AI - Shield Your Inbox",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# প্রফেশনাল ড্যাশবোর্ড স্টাইলিং
st.markdown("""
<style>
    .main-title { font-size: 42px; font-weight: 800; color: #1a73e8; text-align: center; margin-bottom: 10px; }
    .sub-title { font-size: 18px; color: #5f6368; text-align: center; margin-bottom: 40px; }
    .stButton>button { width: 100%; border-radius: 25px; font-weight: bold; transition: 0.3s ease; height: 3.5em; border: none; }
    .stButton>button:hover { box-shadow: 0 4px 15px rgba(26, 115, 232, 0.2); transform: translateY(-2px); }
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 25px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e8eaed; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ব্যবস্থাপনা ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. স্মার্ট প্রোটেকশন ফাংশন ---
def smart_filter(subject, sender):
    """ভালো মেইল রক্ষা করার নিরাপত্তা স্তর"""
    safe_keywords = ["interview", "exam", "otp", "verification", "university", "bkash", "nagad", "appointment"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com", "hackerrank.com"]
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted: {s}"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
    return False, "AI Deep Analysis"

@st.cache_resource
def load_assets():
    """AI মডেল ও ভেক্টরাইজার লোড করা"""
    try:
        model = joblib.load('final_model.pkl')
        vectorizer = joblib.load('final_vectorizer.pkl')
        return model, vectorizer
    except: return None, None

model, vectorizer = load_assets()

def connect_gmail(user, pwd):
    """জিমেইল কানেকশন"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except: return None

# --- ৪. সাইডবার (Login & Control Panel) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    st.title("Control Center")
    if not st.session_state.logged_in:
        u = st.text_input("Gmail Address", placeholder="name@gmail.com")
        p = st.text_input("App Password", type="password", help="Use 16-digit Google App Password")
        with st.expander("❓ Help: App Password"):
            st.markdown("1. Google Account Settings\n2. 2-Step Verification\n3. 'App Passwords'\n4. Copy 16-digit code")
        if st.button("🚀 Connect to Gmail"):
            if u and p:
                if connect_gmail(u, p):
                    st.session_state.logged_in, st.session_state.u, st.session_state.p = True, u, p
                    st.rerun()
                else: st.error("Invalid Credentials.")
    else:
        st.success(f"👤 Connected:\n{st.session_state.u}")
        new_f = st.selectbox("📂 Select Folder", ["INBOX", "[Gmail]/Spam"])
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
st.markdown('<div class="sub-title">Your AI-powered shield against digital noise</div>', unsafe_allow_html=True)

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
                            subject = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sender = msg.get("From", "")
                            is_safe, rule_reason = smart_filter(subject, sender)
                            status, reason = "🔴 Spam", "AI Detected Spam"
                            if is_safe: status, reason = "🟢 Safe", rule_reason
                            elif model and vectorizer:
                                prob = model.predict_proba(vectorizer.transform([subject]))[0][1]
                                if prob < 0.45: status, reason = "🟢 Safe", "AI Verified Safe"
                            data.append({"UID": uid.decode(), "Subject": subject, "Sender": sender, "Verdict": status, "Why?": reason, "Action": False})
                        except: continue
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("✅ Safe", len(df[df['Verdict']=='🟢 Safe']), delta="Inbox")
        c3.metric("🚨 Spam", len(df[df['Verdict']=='🔴 Spam']), delta="-Action", delta_color="inverse")

        st.subheader("📋 Analysis & Security Report")
        col_name = "📥 Select to Process"
        edited_df = st.data_editor(df, column_config={"UID": None, "Action": st.column_config.CheckboxColumn(col_name, default=False)}, hide_index=True, use_container_width=True)
        to_move = edited_df[edited_df['Action'] == True]

        # --- ৬. স্মার্ট অ্যাকশন ইঞ্জিন (Move & Delete) ---
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
                    st.success(f"✨ Successfully moved to {dest}!")
                    time.sleep(1.5)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        # পারমানেন্ট ডিলিট শুধুমাত্র স্প্যাম ফোল্ডারের জন্য
        if st.session_state.current_folder == "[Gmail]/Spam":
            if btn_col2.button("🗑️ Permanently Delete", type="secondary", disabled=len(to_move)==0):
                with st.spinner("Deleting forever..."):
                    try:
                        mail = connect_gmail(st.session_state.u, st.session_state.p)
                        mail.select('"[Gmail]/Spam"')
                        for uid in to_move['UID'].tolist():
                            mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                        mail.expunge() # সার্ভার থেকে স্থায়ীভাবে মুছে ফেলা
                        mail.logout()
                        st.success("🔥 Selected spam emails deleted forever!")
                        time.sleep(1.5)
                        st.session_state.emails_df = pd.DataFrame()
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Welcome! Connect with your App Password to start clean-up.")
