import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ---
st.set_page_config(
    page_title="SpamGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# কাস্টম CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- ৩. হেল্পার ফাংশন ---

def is_important_email(subject, sender):
    safe_keywords = [
        "interview schedule", "appointment letter", "class test", "midterm", "final exam", 
        "cgpa", "grade sheet", "varsity notice", "bkash verification", "nagad otp", 
        "security code", "password reset", "google alert", "verification code", "otp"
    ]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com"]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted Sender ({s})"
    for w in safe_keywords:
        if w in subject: return True, f"Important Keyword: {w}"
    return False, "Potential Spam"

# 🔥 নতুন .pkl ফাইলের নামের সাথে আপডেট করা হয়েছে
@st.cache_resource
def load_ai_model():
    try:
        # আপনার GitHub-এর নতুন ফাইল নামের সাথে মিল রাখা হয়েছে
        with open('final_model.pkl', 'rb') as f:
            model = pickle.load(f)
        with open('final_vectorizer.pkl', 'rb') as f:
            vectorizer = pickle.load(f)
        return model, vectorizer
    except Exception as e:
        st.error(f"Error loading model: {e}")
        return None, None

model, vectorizer = load_ai_model()

def connect_to_gmail(user, pwd):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except:
        return None

# --- ৪. সাইডবার ---
with st.sidebar:
    st.title("🛡️ SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        user_email = st.text_input("Email Address", placeholder="example@gmail.com")
        user_password = st.text_input("App Password", type="password")
        
        if st.button("🚀 Login Securely"):
            if user_email and user_password:
                conn = connect_to_gmail(user_email, user_password)
                if conn:
                    st.session_state.logged_in = True
                    st.session_state.user_email = user_email
                    st.session_state.user_password = user_password
                    conn.logout()
                    st.rerun()
                else:
                    st.error("Login Failed! Use App Password.")
    else:
        st.success(f"👤 Logged in:\n{st.session_state.user_email}")
        folder = st.selectbox("🎯 Target Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("📊 Scan Depth", 10, 100, 50)
        
        if st.button("🔄 Rescan"):
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. ড্যাশবোর্ড ---
if st.session_state.logged_in:
    st.header(f"📂 Scanning: {folder}")
    
    if st.session_state.emails_df.empty:
        with st.spinner("🔍 AI Engine is analyzing your emails..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(folder)
                _, messages = mail.uid('search', None, "ALL")
                
                if messages[0]:
                    uids = messages[0].split()[-limit:]
                    data = []
                    my_bar = st.progress(0)
                    
                    for i, uid in enumerate(reversed(uids)):
                        _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                        msg = email.message_from_bytes(msg_data[0][1])
                        
                        subject = "No Subject"
                        if msg["Subject"]:
                            decoded = decode_header(msg["Subject"])[0]
                            subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                        
                        sender = msg.get("From", "")
                        is_safe, rule_reason = is_important_email(subject, sender)
                        
                        # AI মডেল প্রেডিকশন
                        category, reason = "Spam", "AI Detected Spam"
                        if is_safe:
                            category, reason = "Safe", rule_reason
                        elif model and vectorizer:
                            vec = vectorizer.transform([subject])
                            if model.predict(vec)[0] == 0:
                                category, reason = "Safe", "AI Model Cleared"
                        
                        data.append({
                            "UID": uid.decode('utf-8'),
                            "Subject": subject,
                            "Sender": sender,
                            "Category": category,
                            "Reason": reason,
                            "Delete": True if category == "Spam" else False
                        })
                        my_bar.progress((i + 1) / len(uids))
                    
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    # ডিসপ্লে টেবিল
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("🛡️ Safe", len(df[df['Category']=='Safe']))
        c3.metric("🚨 Spam", len(df[df['Category']=='Spam']))
        
        edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
        
        # ডিলিট লজিক (সংক্ষেপে)
        if st.button("🗑️ Delete Selected"):
            st.warning("Feature: Requires IMAP write access to permanently delete.")

else:
    st.info("👈 Please login from the sidebar using your Gmail App Password.")
