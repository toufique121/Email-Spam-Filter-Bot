import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও থিম ---
st.set_page_config(
    page_title="SpamGuard AI",
    page_icon="🛡️",
    layout="wide"
)

# ইউজার ফ্রেন্ডলি CSS
st.markdown("""
<style>
    .main-title { font-size: 35px; font-weight: 800; color: #1a73e8; text-align: center; }
    .stButton>button { border-radius: 20px; font-weight: bold; height: 3em; }
    .status-safe { color: #1e8e3e; font-weight: bold; }
    .status-spam { color: #d93025; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- ৩. হেল্পার ফাংশন ---

def is_important_email(subject, sender):
    """সুরক্ষা স্তর: ভালো মেইলকে রক্ষা করা"""
    safe_keywords = ["interview", "exam", "otp", "verification", "bkash", "nagad", "university"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com"]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted Domain ({s})"
    for w in safe_keywords:
        if w in subject: return True, f"Vital Keyword ({w})"
    return False, "AI Analysis Required"

@st.cache_resource
def load_ai_model():
    """মডেল লোড করা"""
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

# --- ৪. সাইডবার ---
with st.sidebar:
    st.title("🛡️ SpamGuard AI")
    if not st.session_state.logged_in:
        user_email = st.text_input("Gmail Address")
        user_password = st.text_input("App Password", type="password")
        if st.button("🚀 Access Inbox"):
            if connect_to_gmail(user_email, user_password):
                st.session_state.logged_in = True
                st.session_state.user_email, st.session_state.user_password = user_email, user_password
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.user_email}")
        limit = st.slider("Scan Depth", 10, 100, 50)
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ AI-Powered Spam Organizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner("AI is securing your inbox..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select("INBOX")
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
                            category, reason, status_ui = "Spam", "AI Detected Spam", "🔴 Spam"
                            
                            if is_safe:
                                category, reason, status_ui = "Safe", rule_reason, "🟢 Safe"
                            elif model and vectorizer:
                                prob = model.predict_proba(vectorizer.transform([subject]))[0][1]
                                if prob < 0.40: # ৪০% এর নিচে হলে নিরাপদ
                                    category, reason, status_ui = "Safe", "AI Model Cleared", "🟢 Safe"
                            
                            data.append({"UID": uid.decode('utf-8'), "Subject": subject, "Sender": sender, "Status": status_ui, "Reason": reason, "Move": True if category == "Spam" else False})
                        except: continue
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("✅ Safe", len(df[df['Status']=='🟢 Safe']))
        c3.metric("🚨 Spam", len(df[df['Status']=='🔴 Spam']))

        edited_df = st.data_editor(df, column_config={"UID": None, "Move": st.column_config.CheckboxColumn("🚀 Move to Spam?", default=False)}, hide_index=True, use_container_width=True)

        to_move = edited_df[edited_df['Move'] == True]
        
        # জিমেইল সেটিংস ছাড়াই মেইল সরানোর শক্তিশালী লজিক
        if st.button(f"🚀 Move {len(to_move)} Emails to Spam", type="primary"):
            with st.spinner("Moving..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    mail.select("INBOX")
                    for uid in to_move['UID'].tolist():
                        # ১. মেইলটি স্প্যামে কপি করা
                        mail.uid('COPY', uid.encode('utf-8'), '[Gmail]/Spam')
                        # ২. মেইলটিকে ইনবক্স থেকে মুছে ফেলার জন্য '\Deleted' ফ্ল্যাগ এবং সাথে সাথে সড়িয়ে দেওয়া
                        mail.uid('STORE', uid.encode('utf-8'), '+FLAGS', '\\Deleted')
                    
                    # ৩. সার্ভারকে বাধ্য করা মেইলগুলো এখনই সরাতে (Expunge)
                    mail.expunge() 
                    mail.logout()
                    
                    st.success("Successfully moved! Inbox is now clean. ✨")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Please login with your Gmail App Password.")
