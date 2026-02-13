import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib
import pandas as pd
import time

# --- ১. প্রিমিয়াম UI কনফিগারেশন ---
st.set_page_config(page_title="SpamGuard Pro AI", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .main-title { font-size: 45px; font-weight: 800; color: #1a73e8; text-align: center; }
    .stButton>button { border-radius: 30px; font-weight: bold; height: 3.8em; border: none; transition: 0.3s; }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# --- ২. সেশন স্টেট ব্যবস্থাপনা ---
if 'emails_df' not in st.session_state:
    st.session_state.emails_df = pd.DataFrame()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = "INBOX"

# --- ৩. এআই ও কানেকশন লজিক ---
@st.cache_resource
def load_ai():
    try:
        return joblib.load('final_model.pkl'), joblib.load('final_vectorizer.pkl')
    except: return None, None

model, vectorizer = load_ai()

def connect_gmail(u, p):
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com")
        m.login(u, p)
        return m
    except: return None

# --- ৪. সাইডবার গাইডলাইন (App Standards) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/281/281769.png", width=80)
    if not st.session_state.logged_in:
        st.subheader("🔐 Secure Access")
        u = st.text_input("Gmail Address")
        p = st.text_input("App Password", type="password")
        if st.button("🚀 Sign In"):
            if connect_gmail(u, p):
                st.session_state.logged_in, st.session_state.u, st.session_state.p = True, u, p
                st.rerun()
    else:
        st.success(f"Connected: {st.session_state.u}")
        new_folder = st.selectbox("📂 Folder", ["INBOX", "[Gmail]/Spam"])
        if new_folder != st.session_state.current_folder:
            st.session_state.current_folder = new_folder
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- ৫. প্রোফেশনাল ড্যাশবোর্ড ---
st.markdown('<div class="main-title">🛡️ SpamGuard Pro AI</div>', unsafe_allow_html=True)

if st.session_state.logged_in:
    if st.session_state.emails_df.empty:
        with st.spinner("🔍 AI is optimizing your inbox..."):
            mail = connect_gmail(st.session_state.u, st.session_state.p)
            if mail:
                mail.select(f'"{st.session_state.current_folder}"')
                _, messages = mail.uid('search', None, "ALL")
                if messages[0]:
                    uids = messages[0].split()[-20:]
                    data = []
                    for uid in reversed(uids):
                        try:
                            _, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                            msg = email.message_from_bytes(msg_data[0][1])
                            subj = str(decode_header(msg.get("Subject", "No Subject"))[0][0])
                            sndr = msg.get("From", "")
                            
                            status, action_bool = "🟢 Safe", False
                            if model:
                                prob = model.predict_proba(vectorizer.transform([subj]))[0][1]
                                if prob > 0.45: 
                                    status, action_bool = "🔴 Spam", True # স্প্যাম হলে অটো টিক
                            
                            data.append({"UID": uid.decode(), "Subject": subj, "Sender": sndr, "Verdict": status, "Action": action_bool})
                        except: continue
                    st.session_state.emails_df = pd.DataFrame(data)
                    mail.logout()
                    st.rerun()

    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        c1, c2, c3 = st.columns(3)
        c1.metric("Scanned", len(df))
        c2.metric("Safe", len(df[df['Verdict']=='🟢 Safe']))
        c3.metric("Spam", len(df[df['Verdict']=='🔴 Spam']))

        # স্মার্ট টেবিল যেখানে স্প্যামগুলো আগে থেকেই সিলেক্ট করা থাকবে
        edited_df = st.data_editor(df, column_config={"UID": None, "Action": st.column_config.CheckboxColumn("Select", default=False)}, hide_index=True, use_container_width=True)
        to_move = edited_df[edited_df['Action'] == True]

        # এক ক্লিকে কাজ করার ইঞ্জিন
        col_btn1, col_btn2 = st.columns(2)
        label = "📥 Back to Inbox" if st.session_state.current_folder == "[Gmail]/Spam" else "🚀 Move All Spam"
        
        if col_btn1.button(label, type="primary"):
            with st.spinner("Processing..."):
                try:
                    mail = connect_gmail(st.session_state.u, st.session_state.p)
                    dest = "INBOX" if st.session_state.current_folder == "[Gmail]/Spam" else "[Gmail]/Spam"
                    mail.select(f'"{st.session_state.current_folder}"')
                    for uid in to_move['UID'].tolist():
                        mail.uid('COPY', uid.encode(), f'"{dest}"')
                        mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                    mail.expunge() # সার্ভার সিনক্রোনাইজেশন
                    mail.logout()
                    st.balloons() # সাকসেস অ্যানিমেশন
                    st.success(f"✨ Successfully moved {len(to_move)} items!")
                    time.sleep(1)
                    st.session_state.emails_df = pd.DataFrame()
                    st.rerun()
                except: st.error("Action Failed.")
        
        if st.session_state.current_folder == "[Gmail]/Spam":
            if col_btn2.button("🗑️ Wipe Forever", type="secondary"):
                mail = connect_gmail(st.session_state.u, st.session_state.p)
                mail.select('"[Gmail]/Spam"')
                for uid in to_move['UID'].tolist():
                    mail.uid('STORE', uid.encode(), '+FLAGS', '\\Deleted')
                mail.expunge()
                mail.logout()
                st.success("Spam folder is now empty!")
                st.session_state.emails_df = pd.DataFrame()
                st.rerun()

else:
    st.info("👋 Welcome! Use a Google App Password to keep your inbox clean and secure.")
