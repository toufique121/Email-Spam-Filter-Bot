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

# কাস্টম CSS (UI পোলিশ করার জন্য)
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
    .stTextInput>div>div>input {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'user_password' not in st.session_state:
    st.session_state.user_password = ""

# --- ৩. হেল্পার ফাংশন ---

# 🔥 ফিক্সড হোয়াইটলিস্ট লজিক
def is_important_email(subject, sender):
    safe_keywords = [
        "interview schedule", "appointment letter", "class test", "midterm", "final exam", 
        "cgpa", "grade sheet", "varsity notice", "bkash verification", "nagad otp", 
        "security code", "password reset", "google alert", "verification code", "otp"
    ]
    
    safe_senders = [
        ".edu", ".gov", ".ac.bd", 
        "google.com", "linkedin.com", "github.com", "gitlab.com", "kaggle.com", 
        "streamlit.io", "upwork.com", "fiverr.com", "coursera.org", "udacity.com",
        "hackerrank.com", "codeforces.com"
    ]
    
    sender = sender.lower()
    subject = subject.lower()

    for s in safe_senders:
        if s in sender: return True, f"Trusted Sender ({s})"
    
    for w in safe_keywords:
        if w in subject: return True, f"Important Keyword: {w}"
        
    return False, "Potential Spam"

# মডেল লোড
@st.cache_resource
def load_ai_model():
    try:
        model = pickle.load(open('model.pkl', 'rb'))
        vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
        return model, vectorizer
    except:
        return None, None

model, vectorizer = load_ai_model()

# কানেকশন ফাংশন
def connect_to_gmail(user, pwd):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except Exception as e:
        return None

# --- ৪. সাইডবার (Professional Login Panel) ---
with st.sidebar:
    st.title("🛡️ SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Login")
        
        # ইনপুট ফিল্ড সুন্দর করা হয়েছে
        user_email = st.text_input("Email Address", placeholder="example@gmail.com")
        user_password = st.text_input("App Password", type="password", help="Use Google App Password, NOT your Gmail login password.")
        
        # 🔥🔥🔥 Professional Note Added Here 🔥🔥🔥
        st.info("⚠️ **Note:** This app requires an **'App Password'**.", icon="ℹ️")
        
        with st.expander("❓ How to get App Password?"):
            st.markdown("""
            1. Go to **Google Account** > **Security**.
            2. Enable **2-Step Verification**.
            3. Search for **'App Passwords'**.
            4. Create one (name it 'SpamGuard') and paste the 16-digit code here.
            """)
        
        st.markdown("---")

        if st.button("🚀 Login Securely"):
            if user_email and user_password:
                with st.spinner("Authenticating..."):
                    conn = connect_to_gmail(user_email, user_password)
                    if conn:
                        st.session_state.logged_in = True
                        st.session_state.user_email = user_email
                        st.session_state.user_password = user_password
                        conn.logout()
                        st.success("Login Successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Login Failed! Check Email or App Password.")
            else:
                st.warning("Please fill in all fields.")
                
    else:
        # লগইন পরবর্তী অবস্থা
        st.success(f"👤 Logged in as:\n**{st.session_state.user_email}**")
        
        st.markdown("---")
        st.subheader("⚙️ Scanner Settings")
        
        folder = st.selectbox("🎯 Target Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("📊 Scan Depth (Emails)", 10, 200, 50)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rescan"):
                st.session_state.emails_df = pd.DataFrame()
                st.rerun()
        with col2:
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.session_state.emails_df = pd.DataFrame()
                st.rerun()

# --- ৫. ড্যাশবোর্ড ---

if st.session_state.logged_in:
    st.header(f"📂 Scanning: {folder}")
    
    if st.session_state.emails_df.empty:
        with st.spinner("🔍 AI Engine is analyzing your emails..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(folder)
                status, messages = mail.uid('search', None, "ALL")
                
                if messages[0]:
                    uids = messages[0].split()[-limit:]
                    data = []
                    
                    # প্রোগ্রেস বার
                    progress_text = "Scanning in progress. Please wait..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    for i, uid in enumerate(reversed(uids)):
                        try:
                            res, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            
                            subject = "No Subject"
                            if msg["Subject"]:
                                decoded = decode_header(msg["Subject"])[0]
                                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                            
                            sender = msg.get("From", "")
                            
                            # লজিক
                            category = "Spam"
                            reason = "Unknown"
                            
                            is_safe, rule_reason = is_important_email(subject, sender)
                            
                            if is_safe:
                                category = "Safe"
                                reason = rule_reason
                            elif model:
                                try:
                                    vec = vectorizer.transform([subject])
                                    prediction = model.predict(vec)[0]
                                    if prediction == 0: 
                                        category = "Safe"
                                        reason = "AI Model Cleared"
                                    else: 
                                        category = "Spam"
                                        reason = "AI Detected Spam"
                                except: pass

                            # ইনবক্স সেফটি
                            if folder == "INBOX" and category == "Spam":
                                pass 

                            data.append({
                                "UID": uid.decode('utf-8'),
                                "Subject": subject,
                                "Sender": sender,
                                "Category": category,
                                "Reason": reason,
                                "Delete": True if category == "Spam" else False
                            })
                        except: continue
                        
                        # আপডেট প্রোগ্রেস বার
                        my_bar.progress((i + 1) / len(uids), text=progress_text)
                    
                    my_bar.empty() # কাজ শেষে বার সরিয়ে ফেলা
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                else:
                    st.info("🎉 This folder is completely empty!")
                    mail.logout()

    # রেজাল্ট ডিসপ্লে
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        
        # সুন্দর মেট্রিক্স
        c1, c2, c3 = st.columns(3)
        c1.metric("📬 Total Scanned", len(df))
        c2.metric("🛡️ Safe Emails", len(df[df['Category']=='Safe']), delta="Keep")
        c3.metric("🚨 Spam Detected", len(df[df['Category']=='Spam']), delta="-Delete", delta_color="inverse")
        
        st.divider()
        
        # অ্যাকশন সেন্টার
        tab1, tab2 = st.tabs(["🧹 Cleanup Center", "📄 Detailed Report"])
        
        with tab1:
            st.subheader("Action Required")
            st.caption("Review the emails marked for deletion below.")
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "UID": None, 
                    "Delete": st.column_config.CheckboxColumn("Select to Delete", default=False),
                    "Category": st.column_config.TextColumn("Status", width="small"),
                    "Subject": st.column_config.TextColumn("Subject", width="large"),
                    "Reason": st.column_config.TextColumn("AI Reasoning", width="medium"),
                },
                disabled=["Category", "Subject", "Sender", "Reason", "UID"],
                hide_index=True,
                use_container_width=True,
                height=450
            )
            
            to_delete = edited_df[edited_df['Delete'] == True]
            count = len(to_delete)
            
            # ডিলিট বাটন
            if st.button(f"🗑️ Delete {count} Emails Permanently", type="primary", disabled=(count==0)):
                with st.spinner("Connecting securely to Gmail..."):
                    try:
                        mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                        mail.select(folder)
                        
                        uids_list = to_delete['UID'].tolist()
                        batch_ids = ','.join(uids_list).encode('utf-8')
                        
                        mail.uid('STORE', batch_ids, '+FLAGS', '\\Deleted')
                        mail.expunge()
                        mail.logout()
                        
                        st.toast(f"Success! {count} emails deleted.", icon="✅")
                        time.sleep(1)
                        st.session_state.emails_df = pd.DataFrame()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab2:
            st.dataframe(df, use_container_width=True)

else:
    # লগইন না করা থাকলে মেইন পেজে মেসেজ
    st.info("👈 Please login from the sidebar using your Gmail App Password to start cleaning.")
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=100)
