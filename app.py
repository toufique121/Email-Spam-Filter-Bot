import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ---
st.set_page_config(page_title="SpamGuard Pro AI", page_icon="🛡️", layout="wide")

# প্রফেশনাল ড্যাশবোর্ড CSS
st.markdown("""
<style>
    .main-title { font-size: 38px; font-weight: 800; color: #1a73e8; text-align: center; }
    .stButton>button { width: 100%; border-radius: 20px; font-weight: bold; height: 3.2em; }
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #f1f3f4; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. হেল্পার ফাংশন ---
def is_important_email(subject, sender):
    safe_keywords = ["interview", "exam", "otp", "verification", "university", "bkash", "nagad"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com", "hackerrank.com"]
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted: {s}"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
    return False, "AI Analysis Required"

@st.cache_resource
def load_assets():
    try:
        model = joblib.load('final_model.pkl')
        vectorizer = joblib.load('final_vectorizer.pkl')
        return model, vectorizer
    except: return None, None

model, vectorizer = load_assets()

def connect_gmail(user, pwd):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except: return None

# --- ৪. সাইডবার ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=70)
    if not st.session_state.logged_in:
        u = st.text_input("Gmail Address")
        p = st.text_input("App Password", type="password")
        if st.button("🚀 Connect Inbox"):
            if connect_gmail(u, p):
                st.session_state.logged_in, st.session_state.u, st.session_state.p = True, u, p
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.u}")
        new_f = st.selectbox("📂 Select Folder", ["INBOX", "[Gmail]/Spam"])
        if new_f != st.session_state.current_folder:
            st.session_state.current_folder = new_f
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ AI-Powered Spam Organizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner("🔍 Scanning..."):
            mail = connect_gmail(st.session_state.u, st.session_state.p)
            if mail:
                mail.select(f'"{st.session_state.current_folder}"')
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-20:] # Last 20 scan
                    data = []
                    for uid in reversed(uids):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sender = msg.get("From", "")
                            is_safe, rule_reason = is_important_email(subject, sender)
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
        c2.metric("✅ Safe", len(df[df['Verdict']=='🟢 Safe']))
        c3.metric("🚨 Spam", len(df[df['Verdict']=='🔴 Spam']))

        col_name = "📥 Move to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "🚨 Move to Spam"
        edited_df = st.data_editor(df, column_config={"UID": None, "Action": st.column_config.CheckboxColumn(col_name, default=False)}, hide_index=True, use_container_width=True)

        to_move = edited_df[edited_df['Action'] == True]
        
        # --- ৬. মুভ ইঞ্জিন (The Fix) ---
        if st.button(f"⚡ Execute Action for {len(to_move)} Emails", type="primary", disabled=len(to_move)==0):
            with st.spinner("Executing..."):
                try:
                    mail = connect_gmail(st.session_state.u, st.session_state.p)
                    source = st.session_state.current_folder
                    dest = "INBOX" if source == "[Gmail]/Spam" else "[Gmail]/Spam"
                    
                    mail.select(f'"{source}"')
                    for uid in to_move['UID'].tolist():
                        # মেইল কপি এবং ডিলিট লজিক
                        mail.uid('COPY', uid.encode(), f'"{dest}"')
                        mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                    
                    mail.expunge() # পরিবর্তন কার্যকর করা
                    mail.logout()
                    st.success(f"✨ Successfully moved to {dest}!")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Please connect with your App Password.")
