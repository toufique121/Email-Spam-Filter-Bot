import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. পেজ কনফিগারেশন ও কাস্টম থিমিং ---
st.set_page_config(
    page_title="SpamGuard Pro AI - Shield Your Inbox",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# প্রফেশনাল স্টাইলিং (CSS)
st.markdown("""
<style>
    /* মেইন টাইটেল */
    .main-title { font-size: 42px; font-weight: 800; color: #1a73e8; text-align: center; margin-bottom: 10px; }
    .sub-title { font-size: 18px; color: #5f6368; text-align: center; margin-bottom: 40px; }
    
    /* বাটন ও ইনপুট */
    .stButton>button { width: 100%; border-radius: 25px; font-weight: bold; transition: 0.3s ease; height: 3.5em; border: none; }
    .stButton>button:hover { box-shadow: 0 4px 15px rgba(26, 115, 232, 0.2); transform: translateY(-2px); }
    
    /* কার্ড ও মেট্রিক বক্স */
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 25px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e8eaed; }
    
    /* স্ট্যাটাস ব্যাজ */
    .badge { padding: 4px 12px; border-radius: 12px; font-size: 14px; font-weight: bold; }
    .badge-safe { background-color: #e6f4ea; color: #1e8e3e; }
    .badge-spam { background-color: #fce8e6; color: #d93025; }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট (User Persistence) ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. ইন্টেলিজেন্ট হেল্পার ফাংশন ---
def smart_filter(subject, sender):
    """ভলো মেসেজ যেন স্প্যামে না যায় তার সুরক্ষা স্তর"""
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
    except Exception as e:
        return None, None

model, vectorizer = load_assets()

def connect_gmail(user, pwd):
    """জিমেইল আইম্যাপ কানেকশন"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except:
        return None

# --- ৪. সাইডবার (Login & Control Panel) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    st.title("Control Center")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Access")
        u = st.text_input("Gmail Address", placeholder="name@gmail.com")
        p = st.text_input("App Password", type="password", help="Use 16-digit Google App Password")
        
        with st.expander("❓ Help: App Password"):
            st.markdown("""
            1. Go to **Google Account Settings**.
            2. Enable **2-Step Verification**.
            3. Search **'App Passwords'**.
            4. Create one for 'Other' and copy.
            """)
        
        if st.button("🚀 Connect to Gmail"):
            if u and p:
                with st.spinner("Authenticating..."):
                    if connect_gmail(u, p):
                        st.session_state.logged_in, st.session_state.u, st.session_state.p = True, u, p
                        st.rerun()
                    else:
                        st.error("Invalid Credentials. Check App Password.")
    else:
        st.success(f"👤 Connected:\n{st.session_state.u}")
        st.markdown("---")
        
        st.subheader("⚙️ Settings")
        new_f = st.selectbox("📂 Target Folder", ["INBOX", "[Gmail]/Spam"])
        if new_f != st.session_state.current_folder:
            st.session_state.current_folder = new_f
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
            
        st.session_state.limit = st.select_slider("Scan Depth", options=[10, 20, 50, 100], value=20)
        
        if st.button("🚪 Disconnect"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড (Dashboard Layout) ---
st.markdown('<div class="main-title">🛡️ SpamGuard Pro AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Your AI-powered shield against digital noise</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    # মেইল স্ক্যানিং শুরু
    if st.session_state.emails_df.empty:
        with st.spinner(f"🔍 AI is scanning {st.session_state.current_folder}..."):
            mail = connect_gmail(st.session_state.u, st.session_state.p)
            if mail:
                mail.select(f'"{st.session_state.current_folder}"')
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-st.session_state.limit:]
                    data = []
                    my_bar = st.progress(0)
                    for i, uid in enumerate(reversed(uids)):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sender = msg.get("From", "")
                            
                            is_safe, rule_reason = smart_filter(subject, sender)
                            status, reason = "🔴 Spam", "AI Detected Spam"
                            
                            if is_safe:
                                status, reason = "🟢 Safe", rule_reason
                            elif model and vectorizer:
                                prob = model.predict_proba(vectorizer.transform([subject]))[0][1]
                                if prob < 0.45: # ৪ % এর নিচে হলে নিরাপদ
                                    status, reason = "🟢 Safe", "AI Model Verified"
                            
                            data.append({"UID": uid.decode(), "Subject": subject, "Sender": sender, "Verdict": status, "Why?": reason, "Action": False})
                        except: continue
                        my_bar.progress((i + 1) / len(uids))
                    
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    # স্ট্যাটিস্টিকস কার্ডস
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        col1, col2, col3 = st.columns(3)
        col1.metric("📬 Total Scanned", len(df))
        col2.metric("✅ Verified Safe", len(df[df['Verdict']=='🟢 Safe']), delta="Inbox")
        col3.metric("🚨 Spam Blocked", len(df[df['Verdict']=='🔴 Spam']), delta="-Move", delta_color="inverse")

        st.markdown("---")
        st.subheader("📋 Analysis & Security Report")
        
        # ডাইনামিক চেকবক্স লেবেল
        col_action_name = "📥 Move to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "🚀 Move to Spam"
        
        # ডাটা এডিটর (Clean Table View)
        edited_df = st.data_editor(
            df,
            column_config={
                "UID": None,
                "Action": st.column_config.CheckboxColumn(col_action_name, default=False),
                "Subject": st.column_config.TextColumn("Email Subject", width="large"),
                "Verdict": st.column_config.TextColumn("AI Verdict", width="small")
            },
            hide_index=True,
            use_container_width=True
        )

        # মুভ ইঞ্জিন লজিক
        to_move = edited_df[edited_df['Action'] == True]
        
        if st.button(f"⚡ Execute Action for {len(to_move)} selected emails", type="primary", disabled=len(to_move)==0):
            with st.spinner("Processing..."):
                try:
                    mail = connect_gmail(st.session_state.u, st.session_state.p)
                    source = st.session_state.current_folder
                    dest = "INBOX" if source == "[Gmail]/Spam" else "[Gmail]/Spam"
                    
                    mail.select(f'"{source}"')
                    for uid in to_move['UID'].tolist():
                        mail.uid('COPY', uid.encode(), f'"{dest}"')
                        mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                    
                    mail.expunge() # পরিবর্তন কার্যকর করা
                    mail.logout()
                    
                    st.balloons() # সাকসেস অ্যানিমেশন
                    st.success(f"✨ Successfully organized {len(to_move)} emails!")
                    time.sleep(1.5)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except Exception as e:
                    st.error(f"Something went wrong: {e}")
else:
    # ওয়েলকাম পেজ যখন লগইন নেই
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("👋 **Welcome to SpamGuard Pro!** Connect your Gmail to start clean-up.")
        st.markdown("""
        ### কেন আমাদের বেছে নেবেন?
        * **AI-Powered:** অত্যাধুনিক মেশিন লার্নিং মডেল।
        * **Secure:** সরাসরি গুগল সার্ভারের সাথে এনক্রিপ্টেড কানেকশন।
        * **Smart:** গুরুত্বপূর্ণ মেইল কখনোই হারাবে না।
        """)
    with col2:
        st.image("https://www.gstatic.com/images/branding/product/2x/gmail_64dp.png", width=100)
