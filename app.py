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

# কাস্টম CSS
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

# --- ২. সেশন স্টেট ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'user_password' not in st.session_state:
    st.session_state.user_password = ""

# --- ৩. হেল্পার ফাংশন (আপডেটেড লজিক) ---

# 🔥 ফিক্সড হোয়াইটলিস্ট লজিক (আরও কড়া নিয়ম)
def is_important_email(subject, sender):
    # ১. খুব স্পেসিফিক কিওয়ার্ড (সাধারণ শব্দ বাদ দিয়েছি)
    safe_keywords = [
        "interview schedule", "appointment letter", "class test", "midterm", "final exam", 
        "cgpa", "grade sheet", "varsity notice", "bkash verification", "nagad otp", 
        "security code", "password reset", "google alert"
    ]
    
    # ২. বিশ্বস্ত ডোমেইন (Trusted Domains)
    safe_senders = [
        ".edu", ".gov", ".ac.bd", # শিক্ষা ও সরকারি
        "google.com", "linkedin.com", "github.com", "gitlab.com", "kaggle.com", 
        "streamlit.io", "upwork.com", "fiverr.com", "coursera.org", "udacity.com"
    ]
    
    sender = sender.lower()
    subject = subject.lower()

    # আগে সেন্ডার চেক
    for s in safe_senders:
        if s in sender: return True, f"Trusted Sender ({s})"
    
    # তারপর সাবজেক্ট চেক
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

# --- ৪. সাইডবার ---
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
                    st.error("Login Failed! Check credentials.")
    else:
        st.success(f"User: {st.session_state.user_email}")
        
        st.subheader("⚙️ Settings")
        folder = st.selectbox("Target Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("Scan Emails", 10, 200, 50)
        
        if st.button("🔄 New Scan"):
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
            
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৫. ড্যাশবোর্ড ---

if st.session_state.logged_in:
    st.header("📊 Inbox Health Dashboard")
    
    # স্ক্যানিং প্রসেস
    if st.session_state.emails_df.empty:
        with st.spinner("🤖 AI is analyzing your emails..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            if mail:
                mail.select(folder)
                status, messages = mail.uid('search', None, "ALL")
                
                if messages[0]:
                    uids = messages[0].split()[-limit:]
                    data = []
                    
                    for uid in reversed(uids):
                        try:
                            res, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            
                            subject = "No Subject"
                            if msg["Subject"]:
                                decoded = decode_header(msg["Subject"])[0]
                                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else str(decoded[0])
                            
                            sender = msg.get("From", "")
                            
                            # --- লজিক (Logic) ---
                            category = "Spam"
                            reason = "Unknown"
                            
                            # ১. রুলস চেক
                            is_safe, rule_reason = is_important_email(subject, sender)
                            
                            if is_safe:
                                category = "Safe"
                                reason = rule_reason
                            
                            # ২. AI চেক (যদি রুলসে ধরা না পড়ে)
                            elif model:
                                try:
                                    vec = vectorizer.transform([subject])
                                    prediction = model.predict(vec)[0]
                                    
                                    if prediction == 0: # মডেল বলছে সেফ
                                        category = "Safe"
                                        reason = "AI Model Cleared"
                                    else: # মডেল বলছে স্প্যাম
                                        category = "Spam"
                                        reason = "AI Detected Spam Content"
                                except: 
                                    pass

                            # ইনবক্সের জন্য একটু ছাড় দেওয়া
                            if folder == "INBOX" and category == "Spam":
                                # এখানে চাইলে আরও লজিক দেওয়া যায়
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

    # রেজাল্ট ডিসপ্লে
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        
        # মেট্রিক্স
        c1, c2, c3 = st.columns(3)
        c1.metric("Scanned", len(df))
        c2.metric("Safe", len(df[df['Category']=='Safe']), delta="Keep")
        c3.metric("Spam", len(df[df['Category']=='Spam']), delta="-Delete", delta_color="inverse")
        
        st.divider()
        
        # অ্যাকশন ট্যাব
        tab1, tab2 = st.tabs(["⚡ Clean Up", "📋 Full List"])
        
        with tab1:
            st.subheader("Review Spam Emails")
            
            # এডিটর (UID হাইড করা আছে)
            edited_df = st.data_editor(
                df,
                column_config={
                    "UID": None, 
                    "Delete": st.column_config.CheckboxColumn("Mark for Delete", default=False),
                    "Category": st.column_config.TextColumn("Status", width="small"),
                    "Subject": st.column_config.TextColumn("Subject", width="large"),
                },
                disabled=["Category", "Subject", "Sender", "Reason", "UID"],
                hide_index=True,
                use_container_width=True,
                height=500
            )
            
            to_delete = edited_df[edited_df['Delete'] == True]
            count = len(to_delete)
            
            if st.button(f"🗑️ Delete {count} Emails", type="primary", disabled=(count==0)):
                with st.spinner("Deleting..."):
                    try:
                        mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                        mail.select(folder)
                        
                        # UID লিস্ট নেওয়া
                        uids_list = to_delete['UID'].tolist()
                        batch_ids = ','.join(uids_list).encode('utf-8')
                        
                        # ডিলিট কমান্ড
                        mail.uid('STORE', batch_ids, '+FLAGS', '\\Deleted')
                        mail.expunge()
                        mail.logout()
                        
                        st.toast(f"Boom! {count} emails deleted.", icon="💥")
                        time.sleep(1)
                        st.session_state.emails_df = pd.DataFrame()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab2:
            st.dataframe(df)

else:
    st.info("👈 Please login from the sidebar.")
