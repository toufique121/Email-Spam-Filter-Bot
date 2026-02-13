import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও প্রিমিয়াম থিম ---
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

# --- ৩. স্মার্ট প্রোটেকশন ফাংশন (Smart Filter) ---
def is_important_email(subject, sender):
    """ভালো মেইল রক্ষা করার লেয়ার"""
    safe_keywords = ["interview", "exam", "otp", "verification", "university", "bkash", "nagad", "appointment", "schedule"]
    safe_senders = [".edu", ".gov", ".ac.bd", "google.com", "linkedin.com", "github.com", "kaggle.com", "hackerrank.com"]
    
    sender, subject = sender.lower(), subject.lower()
    for s in safe_senders:
        if s in sender: return True, f"Trusted: {s}"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
    return False, "AI Analysis Required"

@st.cache_resource
def load_ai_model():
    """AI মডেল লোড"""
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

# --- ৪. সাইডবার (Login, Folder & Instructions) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=70)
    st.title("SpamGuard Pro AI")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        user_email = st.text_input("Gmail Address", placeholder="example@gmail.com")
        user_password = st.text_input("App Password", type="password", help="Use 16-digit Google App Password")
        
        # 💡 App Password কেন প্রয়োজন তার বর্ণনা
        with st.expander("❓ Why App Password?"):
            st.markdown("""
            আপনার মূল পাসওয়ার্ড এখানে কাজ করবে না। 
            ১. Google Account-এ গিয়ে **2-Step Verification** চালু করুন।
            ২. সার্চ বারে **'App Passwords'** লিখে সার্চ করুন।
            ৩. একটি নাম দিয়ে **Create** করুন এবং ১৬ সংখ্যার কোডটি এখানে ব্যবহার করুন।
            """)
        
        if st.button("🚀 Connect Inbox"):
            if user_email and user_password:
                with st.spinner("Connecting..."):
                    if connect_to_gmail(user_email, user_password):
                        st.session_state.logged_in = True
                        st.session_state.user_email, st.session_state.user_password = user_email, user_password
                        st.rerun()
                    else:
                        st.error("❌ Login Failed! Use 'App Password' only.")
    else:
        st.success(f"👤 {st.session_state.user_email}")
        
        # ফোল্ডার পরিবর্তন লজিক
        new_folder = st.selectbox("📂 Select Folder", ["INBOX", "[Gmail]/Spam"])
        if new_folder != st.session_state.current_folder:
            st.session_state.current_folder = new_folder
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
            
        limit = st.slider("Scan Depth", 10, 100, 50)
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ AI-Powered Spam Organizer</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner(f"🔍 AI is scanning {st.session_state.current_folder}..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(st.session_state.current_folder)
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
                                if prob < 0.40: # Strict Threshold
                                    category, reason, status_ui = "Safe", "AI Model Cleared", "🟢 Safe"
                            
                            data.append({
                                "UID": uid.decode('utf-8'), 
                                "Subject": subject, 
                                "Sender": sender, 
                                "Verdict": status_ui, 
                                "Why?": reason, 
                                "Action?": True if category == "Spam" else False
                            })
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

        st.subheader("📋 Analysis Report")
        
        # ডাইনামিক বাটন টেক্সট সেট করা
        btn_label = "Move to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "Move to Spam"
        
        edited_df = st.data_editor(
            df, 
            column_config={
                "UID": None, 
                "Action?": st.column_config.CheckboxColumn(btn_label, default=False)
            }, 
            hide_index=True, 
            use_container_width=True
        )

        to_action = edited_df[edited_df['Action?'] == True]
        
        # --- ৬. স্মার্ট অ্যাকশন ইঞ্জিন (Inbox <-> Spam) ---
        if st.button(f"⚡ Execute Action for {len(to_action)} Emails", type="primary", disabled=len(to_action)==0):
            with st.spinner("Processing..."):
                try:
                    mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                    source_folder = st.session_state.current_folder
                    
                    for index, row in to_action.iterrows():
                        uid = row['UID']
                        mail.select(source_folder)
                        
                        # স্প্যাম থেকে ইনবক্সে পাঠানোর লজিক
                        if source_folder == "[Gmail]/Spam":
                            mail.uid('COPY', uid.encode('utf-8'), 'INBOX')
                        # ইনবক্স থেকে স্প্যামে পাঠানোর লজিক
                        else:
                            mail.uid('COPY', uid.encode('utf-8'), '[Gmail]/Spam')
                        
                        # সোর্স ফোল্ডার থেকে রিমুভ করা
                        mail.uid('STORE', uid.encode('utf-8'), '+FLAGS', '\\Deleted')
                    
                    mail.expunge() # সেটিংস ছাড়াই মেইল সরানোর মূল কমান্ড
                    mail.logout()
                    st.success(f"✨ Successfully organized {len(to_action)} emails!")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
else:
    st.info("👋 Please connect your account with a **Google App Password** to start AI protection.")
