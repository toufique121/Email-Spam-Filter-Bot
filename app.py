import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px
import time

# --- ১. পেজ কনফিগারেশন ---
st.set_page_config(
    page_title="SpamGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# কাস্টম CSS (সুন্দর ডিজাইনের জন্য)
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট (মেমোরি ম্যানেজমেন্ট) ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'user_password' not in st.session_state:
    st.session_state.user_password = ""

# --- ৩. হেল্পার ফাংশন ---

# হোয়াইটলিস্ট লজিক
def is_important_email(subject, sender):
    safe_keywords = [
        "interview", "offer", "job", "hiring", "application", "resume", "cv",
        "class", "exam", "quiz", "assignment", "grade", "result", "university",
        "bkash", "nagad", "otp", "verification", "code", "invoice", "payment",
        "login", "security", "alert"
    ]
    safe_senders = [
        ".edu", ".gov", ".org", "google.com", "linkedin.com", "facebook.com",
        "github.com", "gitlab.com", "kaggle.com", "streamlit.io", "upwork.com"
    ]
    
    sender = sender.lower()
    subject = subject.lower()

    for s in safe_senders:
        if s in sender: return True, f"Trusted Sender ({s})"
    for w in safe_keywords:
        if w in subject: return True, f"Keyword: {w}"
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

# IMAP কানেকশন
def connect_to_gmail(user, pwd):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except Exception as e:
        return None

# --- ৪. সাইডবার (Login & Settings) ---
with st.sidebar:
    st.title("🛡️ SpamGuard AI")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        user_email = st.text_input("Gmail Address")
        user_password = st.text_input("App Password", type="password")
        if st.button("🔐 Login"):
            if user_email and user_password:
                conn = connect_to_gmail(user_email, user_password)
                if conn:
                    st.session_state.logged_in = True
                    st.session_state.user_email = user_email
                    st.session_state.user_password = user_password
                    conn.logout()
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Login Failed! Check email or app password.")
    else:
        st.success(f"Logged in as: {st.session_state.user_email}")
        
        st.subheader("⚙️ Scanner Settings")
        folder = st.selectbox("Target Folder", ["[Gmail]/Spam", "INBOX"])
        limit = st.slider("Scan Depth", 10, 200, 50)
        
        if st.button("🔄 Refresh / New Scan"):
            st.session_state.emails_df = pd.DataFrame() # Clear Data
            st.rerun()
            
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. মেইন ড্যাশবোর্ড ---

if st.session_state.logged_in:
    st.header("📊 Dashboard Overview")
    
    # স্ক্যান লজিক (যদি ডাটা না থাকে)
    if st.session_state.emails_df.empty:
        with st.spinner("🚀 AI Engine Scanning your emails..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(folder)
                
                status, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-limit:] # Latest emails
                    
                    data = []
                    # লেটেস্ট মেইল আগে পাওয়ার জন্য রিভার্স লুপ
                    for uid in reversed(uids):
                        try:
                            res, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            
                            # ডিকোডিং সাবজেক্ট
                            subject = "No Subject"
                            if msg["Subject"]:
                                decoded = decode_header(msg["Subject"])[0]
                                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                            
                            sender = msg.get("From", "")
                            
                            # --- AI & Rules Logic ---
                            category = "Spam"
                            reason = "Unknown"
                            
                            # 1. Whitelist Check
                            is_safe, rule_reason = is_important_email(subject, sender)
                            if is_safe:
                                category = "Safe"
                                reason = rule_reason
                            
                            # 2. AI Check (যদি রুলসে স্প্যাম হয়)
                            elif model:
                                try:
                                    vec = vectorizer.transform([subject])
                                    if model.predict(vec)[0] == 0: # 0 means Safe/Ham usually
                                        category = "Safe"
                                        reason = "AI Model (Safe)"
                                    else:
                                        reason = "High Risk Content"
                                except: pass
                                
                            # INBOX এর জন্য ডিফল্ট বিহেভিয়ার
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
                    
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                else:
                    st.info("Folder is empty!")
                    mail.logout()
    
    # --- ডিসপ্লে সেকশন (যদি ডাটা থাকে) ---
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        
        # 1. Top Metrics
        col1, col2, col3, col4 = st.columns(4)
        total = len(df)
        spam = len(df[df['Category'] == 'Spam'])
        safe = len(df[df['Category'] == 'Safe'])
        
        col1.metric("Total Emails", total)
        col2.metric("Safe Emails", safe, delta="Protected 🛡️")
        col3.metric("Spam Detected", spam, delta="-Risk 🚨", delta_color="inverse")
        
        # 2. Chart
        with col4:
            if spam > 0:
                fig = px.pie(df, names='Category', color='Category', 
                             color_discrete_map={'Safe':'#00cc96', 'Spam':'#EF553B'},
                             hole=0.4)
                fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=100)
                st.plotly_chart(fig, use_container_width=True)
        
        st.divider()

        # 3. Tabs for Better UI
        tab1, tab2 = st.tabs(["⚡ Action Center", "📝 Detailed List"])
        
        with tab1:
            st.subheader("Review & Clean")
            st.caption("Uncheck items if you want to keep them. Then click 'Delete'.")
            
            # --- 🔥 CRITICAL FIX: UID কলাম লুকিয়ে রাখা কিন্তু ডাটাফ্রেমে রাখা ---
            edited_df = st.data_editor(
                df, # পুরো ডাটাফ্রেম দিচ্ছি (UID সহ)
                column_config={
                    "UID": None, # 👈 ইউজার এটি দেখবে না
                    "Delete": st.column_config.CheckboxColumn("Mark for Deletion", default=False),
                    "Category": st.column_config.TextColumn("Status", width="small"),
                    "Subject": st.column_config.TextColumn("Subject", width="large"),
                    "Reason": st.column_config.TextColumn("Reason", width="medium"),
                },
                disabled=["Category", "Subject", "Sender", "Reason", "UID"],
                hide_index=True,
                use_container_width=True,
                height=400
            )
            
            # --- ডিলিট লজিক ---
            to_delete = edited_df[edited_df['Delete'] == True]
            count = len(to_delete)
            
            col_btn1, col_btn2 = st.columns([1, 4])
            
            with col_btn1:
                if st.button(f"🗑️ Delete {count} Emails", type="primary", disabled=(count==0)):
                    with st.spinner("Connecting securely and deleting..."):
                        try:
                            # ডিলিট করার জন্য আবার কানেক্ট করা
                            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                            mail.select(folder)
                            
                            # UID গুলো সংগ্রহ করা
                            uids_to_remove = to_delete['UID'].tolist()
                            
                            # একসাথে ডিলিট (Batch Delete)
                            batch_ids = ','.join(uids_to_remove).encode('utf-8')
                            
                            # ১. মার্ক ডিলিট
                            mail.uid('STORE', batch_ids, '+FLAGS', '\\Deleted')
                            # ২. এক্সপাঞ্জ (স্থায়ী ডিলিট)
                            mail.expunge()
                            mail.logout()
                            
                            st.toast(f"✅ Successfully deleted {count} emails!", icon="🎉")
                            time.sleep(1)
                            
                            # মেমোরি ক্লিয়ার করে রিফ্রেশ
                            st.session_state.emails_df = pd.DataFrame() 
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error during deletion: {e}")

        with tab2:
            st.dataframe(df, use_container_width=True)

else:
    st.info("👈 Please login from the sidebar to access the dashboard.")
