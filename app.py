import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib  # মডেল লোড করার জন্য pickle এর চেয়ে বেশি নির্ভরযোগ্য
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ---
st.set_page_config(
    page_title="SpamGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# কাস্টম CSS (UI সুন্দর করার জন্য)
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
    """ম্যানুয়াল রুলস ব্যবহার করে গুরুত্বপূর্ণ মেইল আলাদা করা"""
    safe_keywords = [
        "interview schedule", "appointment letter", "class test", "midterm", "final exam", 
        "cgpa", "grade sheet", "varsity notice", "bkash verification", "nagad otp", 
        "security code", "password reset", "google alert", "verification code", "otp"
    ]
    # আপনার প্রয়োজনীয় ডোমেইনগুলো এখানে আপডেট করা হয়েছে
    safe_senders = [
        ".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", 
        "kaggle.com", "codeforces.com", "hackerrank.com", "streamlit.io",
        "upwork.com", "fiverr.com", "coursera.org", "udacity.com"
    ]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted Sender ({s})"
    for w in safe_keywords:
        if w in subject: return True, f"Important Keyword: {w}"
    return False, "Potential Spam"

@st.cache_resource
def load_ai_model():
    """joblib ব্যবহার করে AI মডেল ও ভেক্টরাইজার লোড করা"""
    try:
        # নিশ্চিত করুন আপনার GitHub-এ ফাইলের নাম 'final_model.pkl' এবং 'final_vectorizer.pkl'
        model = joblib.load('final_model.pkl')
        vectorizer = joblib.load('final_vectorizer.pkl')
        return model, vectorizer
    except Exception as e:
        st.error(f"Error loading model: {e}")
        return None, None

model, vectorizer = load_ai_model()

def connect_to_gmail(user, pwd):
    """জিমেইল সার্ভারের সাথে কানেক্ট করা"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except:
        return None

# --- ৪. সাইডবার (Login & Settings) ---
with st.sidebar:
    st.title("🛡️ SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        user_email = st.text_input("Email Address", placeholder="example@gmail.com")
        user_password = st.text_input("App Password", type="password", help="Use Google App Password.")
        
        if st.button("🚀 Login Securely"):
            if user_email and user_password:
                with st.spinner("Authenticating..."):
                    conn = connect_to_gmail(user_email, user_password)
                    if conn:
                        st.session_state.logged_in = True
                        st.session_state.user_email = user_email
                        st.session_state.user_password = user_password
                        conn.logout()
                        st.rerun()
                    else:
                        st.error("Login Failed! Check Email or App Password.")
    else:
        st.success(f"👤 Logged in:\n{st.session_state.user_email}")
        folder = st.selectbox("🎯 Target Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("📊 Scan Depth (Emails)", 10, 200, 50)
        
        if st.button("🔄 Rescan"):
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. ড্যাশবোর্ড ও এআই এনালাইসিস ---
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
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            
                            subject = "No Subject"
                            if msg["Subject"]:
                                decoded = decode_header(msg["Subject"])[0]
                                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                            
                            sender = msg.get("From", "")
                            is_safe, rule_reason = is_important_email(subject, sender)
                            
                            category, reason = "Spam", "AI Detected Spam"
                            if is_safe:
                                category, reason = "Safe", rule_reason
                            elif model and vectorizer:
                                vec = vectorizer.transform([subject])
                                if model.predict(vec)[0] == 0:  # 0 = Ham, 1 = Spam
                                    category, reason = "Safe", "AI Model Cleared"
                            
                            data.append({
                                "UID": uid.decode('utf-8'),
                                "Subject": subject,
                                "Sender": sender,
                                "Category": category,
                                "Reason": reason,
                                "Delete": True if category == "Spam" else False
                            })
                        except:
                            continue
                        my_bar.progress((i + 1) / len(uids))
                    
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    # রেজাল্ট ডিসপ্লে টেবিল
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Scanned", len(df))
        c2.metric("🛡️ Safe Emails", len(df[df['Category']=='Safe']), delta="Keep")
        c3.metric("🚨 Spam Detected", len(df[df['Category']=='Spam']), delta="-Delete", delta_color="inverse")
        
        st.divider()
        st.subheader("🧹 Action Required")
        
        # ডাটা এডিটর ব্যবহার করে ইউজারকে ডিলিট করার সুযোগ দেওয়া
        edited_df = st.data_editor(
            df,
            column_config={
                "UID": None, 
                "Delete": st.column_config.CheckboxColumn("Select to Delete", default=False),
                "Category": st.column_config.TextColumn("Status", width="small"),
            },
            disabled=["Category", "Subject", "Sender", "Reason", "UID"],
            hide_index=True,
            use_container_width=True
        )
        
        # আসল ডিলিট লজিক
        to_delete = edited_df[edited_df['Delete'] == True]
        count = len(to_delete)
        
        if st.button(f"🗑️ Delete {count} Selected Emails", type="primary", disabled=(count==0)):
            with st.spinner("Deleting from Gmail..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    mail.select(folder)
                    
                    uids_to_del = to_delete['UID'].tolist()
                    for uid in uids_to_del:
                        # মেইলগুলোকে জিমেইলের ট্র্যাশ বা ডিলিট ফ্ল্যাগে পাঠানো
                        mail.uid('STORE', uid.encode('utf-8'), '+FLAGS', '\\Deleted')
                    
                    mail.expunge()
                    mail.logout()
                    
                    st.toast(f"Success! {count} emails removed.", icon="✅")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.info("👈 Please login from the sidebar using your Gmail App Password to start scanning.")
