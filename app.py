import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও থিম ---
st.set_page_config(
    page_title="SpamGuard Pro AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# প্রফেশনাল ড্যাশবোর্ড CSS
st.markdown("""
<style>
    .main-title { font-size: 38px; font-weight: 800; color: #1a73e8; text-align: center; margin-bottom: 25px; }
    .stButton>button { width: 100%; border-radius: 20px; font-weight: bold; transition: 0.3s; height: 3.2em; }
    .stButton>button:hover { background-color: #1a73e8; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f1f3f4; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ব্যবস্থাপনা ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. স্মার্ট ফিল্টার ফাংশন ---
def is_important_email(subject, sender):
    """ভালো মেইল রক্ষা করার লেয়ার"""
    safe_keywords = ["interview", "exam", "otp", "verification", "university", "bkash", "nagad", "coding"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com", "hackerrank.com"]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted: {s}"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
    return False, "AI Analysis Required"

@st.cache_resource
def load_ai_model():
    """AI মডেল লোড করা"""
    try:
        model = joblib.load('final_model.pkl')
        vectorizer = joblib.load('final_vectorizer.pkl')
        return model, vectorizer
    except: return None, None

model, vectorizer = load_ai_model()

def connect_to_gmail(user, pwd):
    """জিমেইল কানেকশন"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except: return None

# --- ৪. সাইডবার (Login & Selection) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=70)
    st.title("SpamGuard Pro AI")
    
    if not st.session_state.logged_in:
        user_email = st.text_input("Gmail Address")
        user_password = st.text_input("App Password", type="password")
        
        with st.expander("❓ How to get App Password?"):
            st.markdown("Google Account > 2-Step Verification > App Passwords.")
            
        if st.button("🚀 Connect Inbox"):
            if connect_to_gmail(user_email, user_password):
                st.session_state.logged_in = True
                st.session_state.user_email, st.session_state.user_password = user_email, user_password
                st.rerun()
            else: st.error("❌ Login Failed!")
    else:
        st.success(f"👤 {st.session_state.user_email}")
        new_folder = st.selectbox("📂 Select Folder", ["INBOX", "[Gmail]/Spam"])
        if new_folder != st.session_state.current_folder:
            st.session_state.current_folder = new_folder
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        limit = st.slider("Scan Depth", 10, 100, 50)
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ AI-Powered Spam Organizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner(f"🔍 Analyzing {st.session_state.current_folder}..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(st.session_state.current_folder)
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-limit:]
                    data = []
                    for uid in reversed(uids):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sender = msg.get("From", "")
                            
                            is_safe, rule_reason = is_important_email(subject, sender)
                            status_ui, category = "🔴 Spam", "Spam"
                            
                            if is_safe: status_ui, category = "🟢 Safe", "Safe"
                            elif model and vectorizer:
                                prob = model.predict_proba(vectorizer.transform([subject]))[0][1]
                                if prob < 0.40: status_ui, category = "🟢 Safe", "Safe"
                            
                            data.append({"UID": uid.decode(), "Subject": subject, "Sender": sender, "Verdict": status_ui, "Select": False})
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

        # ফোল্ডার অনুযায়ী লেবেল পরিবর্তন
        col_label = "📥 Move to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "🚨 Move to Spam"
        
        st.subheader("📋 Analysis Report")
        edited_df = st.data_editor(df, column_config={"UID": None, "Select": st.column_config.CheckboxColumn(col_label, default=False)}, hide_index=True, use_container_width=True)

        to_action = edited_df[edited_df['Select'] == True]
        
        # --- ৬. স্মার্ট মুভ ইঞ্জিন (Recovery) ---
        if st.button(f"⚡ Execute Action for {len(to_action)} Emails", type="primary", disabled=len(to_action)==0):
            with st.spinner("Processing..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    source = st.session_state.current_folder
                    dest = "INBOX" if source == "[Gmail]/Spam" else "[Gmail]/Spam"
                    
                    mail.select(source)
                    for uid in to_action['UID'].tolist():
                        mail.uid('COPY', uid.encode(), dest)
                        mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                    
                    mail.expunge() # সেটিংস ছাড়াই কার্যকর করার কমান্ড
                    mail.logout()
                    st.success(f"✨ Moved {len(to_action)} emails to {dest}!")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Please connect with your App Password to start.")
