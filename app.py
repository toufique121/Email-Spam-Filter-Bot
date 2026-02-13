import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও প্রিমিয়াম থিম ---
st.set_page_config(
    page_title="SpamGuard AI - Shield Your Inbox",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# প্রফেশনাল ড্যাশবোর্ড CSS
st.markdown("""
<style>
    .main-title { font-size: 40px; font-weight: 800; color: #1a73e8; text-align: center; margin-bottom: 30px; }
    .stButton>button { width: 100%; border-radius: 20px; font-weight: bold; transition: 0.3s; height: 3em; }
    .stButton>button:hover { background-color: #1a73e8; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f1f3f4; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- ৩. স্মার্ট প্রোটেকশন ফাংশন ---
def is_important_email(subject, sender):
    """ভালো মেইল রক্ষা করার নিরাপত্তা স্তর"""
    safe_keywords = ["interview", "appointment", "class test", "exam", "otp", "verification", "bkash", "nagad", "university"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com", "codeforces.com", "hackerrank.com", "streamlit.io"]
    
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
    except Exception as e:
        st.error(f"❌ Model Error: {e}")
        return None, None

model, vectorizer = load_ai_model()

def connect_to_gmail(user, pwd):
    """জিমেইল কানেকশন"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except:
        return None

# --- ৪. সাইডবার (Login & Settings) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    st.title("SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        user_email = st.text_input("Gmail Address", placeholder="example@gmail.com")
        user_password = st.text_input("App Password", type="password")
        
        with st.expander("❓ How to get App Password?"):
            st.markdown("1. Go to Google Account Settings.\n2. Enable 2-Step Verification.\n3. Search 'App Passwords'.\n4. Copy 16-digit code.")
        
        if st.button("🚀 Access Inbox"):
            if user_email and user_password:
                if connect_to_gmail(user_email, user_password):
                    st.session_state.logged_in = True
                    st.session_state.user_email, st.session_state.user_password = user_email, user_password
                    st.rerun()
                else:
                    st.error("❌ Login Failed!")
    else:
        st.success(f"👤 {st.session_state.user_email}")
        folder = st.selectbox("📂 Scan Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("📊 Scan Depth", 10, 100, 50)
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড (The Professional View) ---
st.markdown('<div class="main-title">🛡️ AI-Powered Spam Organizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner("🧠 AI is analyzing patterns..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(folder)
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-limit:]
                    data = []
                    my_bar = st.progress(0)
                    for i, uid in enumerate(reversed(uids)):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sender = msg.get("From", "")
                            
                            is_safe, rule_reason = is_important_email(subject, sender)
                            category, reason, status_ui = "Spam", "AI Detected Spam", "🔴 Spam"
                            
                            if is_safe:
                                category, reason, status_ui = "Safe", rule_reason, "🟢 Safe"
                            elif model and vectorizer:
                                prob = model.predict_proba(vectorizer.transform([subject]))[0][1]
                                if prob < 0.40: # ৪০% থ্রেশহোল্ড
                                    category, reason, status_ui = "Safe", "AI Model Cleared", "🟢 Safe"
                            
                            data.append({"UID": uid.decode('utf-8'), "Subject": subject, "Sender": sender, "Verdict": status_ui, "Why?": reason, "Move to Spam?": True if category == "Spam" else False})
                        except: continue
                        my_bar.progress((i + 1) / len(uids))
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("✅ Safe", len(df[df['Verdict']=='🟢 Safe']))
        c3.metric("🚨 Spam", len(df[df['Verdict']=='🔴 Spam']))

        st.markdown("### 🔍 Security Report")
        edited_df = st.data_editor(df, column_config={"UID": None, "Move to Spam?": st.column_config.CheckboxColumn(default=False)}, hide_index=True, use_container_width=True)

        to_move = edited_df[edited_df['Move to Spam?'] == True]
        
        # প্রফেশনাল মুভ বাটন
        if st.button(f"🚀 Move {len(to_move)} Selected Emails to Spam Folder", type="primary", disabled=len(to_move)==0):
            with st.spinner("Moving to [Gmail]/Spam..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    mail.select("INBOX")
                    for uid in to_move['UID'].tolist():
                        mail.uid('COPY', uid.encode('utf-8'), '[Gmail]/Spam')
                        mail.uid('STORE', uid.encode('utf-8'), '+FLAGS', '\\Deleted')
                    mail.expunge() # সেটিংস ছাড়াই কার্যকর করার কমান্ড
                    mail.logout()
                    st.success("Successfully moved to Spam folder! ✨")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Please login with your Gmail App Password to protect your inbox.")
