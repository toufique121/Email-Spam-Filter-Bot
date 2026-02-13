import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও প্রিমিয়াম থিম ---
st.set_page_config(
    page_title="SpamGuard AI - Shield Your Inbox",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# কাস্টম CSS (ডিজাইন আকর্ষণীয় করার জন্য)
st.markdown("""
<style>
    /* মেইন টাইটেল স্টাইল */
    .main-title {
        font-size: 40px;
        font-weight: 800;
        color: #1a73e8;
        text-align: center;
        margin-bottom: 30px;
    }
    /* বাটন স্টাইল */
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        border: none;
        transition: 0.3s;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1a73e8;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    /* মেট্রিক বক্স স্টাইল */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f1f3f4;
    }
    /* স্ট্যাটাস ব্যাজ */
    .status-safe { color: #1e8e3e; font-weight: bold; background-color: #e6f4ea; padding: 2px 8px; border-radius: 10px; }
    .status-spam { color: #d93025; font-weight: bold; background-color: #fce8e6; padding: 2px 8px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- ৩. হেল্পার ফাংশন ---

def is_important_email(subject, sender):
    """ম্যানুয়াল রুলস ব্যবহার করে নিরাপদ মেইল আলাদা করা"""
    safe_keywords = [
        "interview", "appointment", "class test", "midterm", "final exam", 
        "cgpa", "grade", "notice", "bkash", "nagad", "otp", "verification", "security"
    ]
    safe_senders = [
        ".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", 
        "kaggle.com", "codeforces.com", "hackerrank.com", "streamlit.io", "upwork.com"
    ]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted: {s}"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
    return False, "AI Analysis Required"

@st.cache_resource
def load_ai_model():
    """AI মডেল ও ভেক্টরাইজার লোড করা"""
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

# --- ৪. সাইডবার (Login & Instructions) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    st.title("SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        user_email = st.text_input("Gmail Address", placeholder="yourname@gmail.com")
        user_password = st.text_input("App Password", type="password", help="Enter 16-digit App Password")
        
        # 🔥 App Password Instruction
        with st.expander("❓ How to get App Password?"):
            st.markdown("""
            1. Go to **Google Account Settings**.
            2. Enable **2-Step Verification**.
            3. Search for **'App Passwords'**.
            4. Choose **'Other'**, name it 'SpamGuard'.
            5. Copy the **16-digit code** and paste here.
            """)
        
        if st.button("🚀 Access Inbox"):
            if user_email and user_password:
                with st.spinner("Connecting securely..."):
                    conn = connect_to_gmail(user_email, user_password)
                    if conn:
                        st.session_state.logged_in = True
                        st.session_state.user_email = user_email
                        st.session_state.user_password = user_password
                        conn.logout()
                        st.rerun()
                    else:
                        st.error("❌ Login Failed! Use 'App Password' only.")
    else:
        st.success(f"👤 Account: \n{st.session_state.user_email}")
        folder = st.selectbox("📂 Scan Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("📊 Emails to Scan", 10, 200, 50)
        
        st.markdown("---")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ SpamGuard AI Engine</div>', unsafe_allow_html=True)

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
                            
                            subject = "No Subject"
                            if msg["Subject"]:
                                decoded = decode_header(msg["Subject"])[0]
                                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                            
                            sender = msg.get("From", "")
                            is_safe, rule_reason = is_important_email(subject, sender)
                            
                            category, reason, status_ui = "Spam", "AI Detected Spam", "🔴 Spam"
                            
                            if is_safe:
                                category, reason, status_ui = "Safe", rule_reason, "🟢 Safe"
                            elif model and vectorizer:
                                vec = vectorizer.transform([subject])
                                # থ্রেশহোল্ড চেক করে কড়া ফিল্টারিং
                                probs = model.predict_proba(vec)[0]
                                if probs[1] < 0.35: # Spam probability < 35%
                                    category, reason, status_ui = "Safe", "AI Model Cleared", "🟢 Safe"
                            
                            data.append({
                                "UID": uid.decode('utf-8'),
                                "Subject": subject,
                                "Sender": sender,
                                "Status": status_ui,
                                "Reason": reason,
                                "Select": True if category == "Spam" else False
                            })
                        except: continue
                        my_bar.progress((i + 1) / len(uids))
                    
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    # ডাটা ভিজুয়ালাইজেশন
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Total Scanned", len(df))
        c2.metric("✅ Safe & Sound", len(df[df['Status']=='🟢 Safe']))
        c3.metric("🚨 Spam Blocked", len(df[df['Status']=='🔴 Spam']))
        
        st.markdown("### 🔍 Security Report")
        
        # এডিটর টেবিল
        edited_df = st.data_editor(
            df,
            column_config={
                "UID": None, 
                "Select": st.column_config.CheckboxColumn("🗑️ Delete?", default=False),
                "Status": st.column_config.TextColumn("Verdict"),
                "Subject": st.column_config.TextColumn("Email Subject", width="large"),
                "Reason": st.column_config.TextColumn("Why?"),
            },
            disabled=["Status", "Subject", "Sender", "Reason", "UID"],
            hide_index=True,
            use_container_width=True
        )
        
        # ডিলিট অ্যাকশন
        to_delete = edited_df[edited_df['Select'] == True]
        if st.button(f"🧹 Clean Up {len(to_delete)} Selected Emails", type="primary"):
            with st.spinner("Deleting permanently..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    mail.select(folder)
                    for uid in to_delete['UID'].tolist():
                        mail.uid('STORE', uid.encode('utf-8'), '+FLAGS', '\\Deleted')
                    mail.expunge()
                    mail.logout()
                    st.toast("Inbox Cleaned Successfully! ✨")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    # লগইন না থাকলে সুন্দর একটি ওয়েলকাম মেসেজ
    st.info("👋 Welcome! Please login from the sidebar using your **Gmail App Password** to protect your inbox.")
    st.markdown("""
    ### কেন 'App Password' প্রয়োজন? 
    আপনার মূল জিমেইল পাসওয়ার্ড দিয়ে লগইন করা আপনার অ্যাকাউন্টের জন্য অনিরাপদ। 
    **Google App Password** ব্যবহার করলে আপনার অ্যাকাউন্ট ১০০% নিরাপদ থাকে এবং আপনার এই 
    SpamGuard AI অ্যাপটি আপনার হয়ে ইনবক্স পরিষ্কার করার অনুমতি পায়।
    """)
    st.image("https://www.gstatic.com/images/branding/product/2x/gmail_64dp.png", width=50)
