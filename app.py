import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import time
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# --- ১. পেজ এবং ফাইল কনফিগারেশন ---
st.set_page_config(page_title="Smart Spam Cleaner", page_icon="🧠", layout="wide")

# ফাইলের নাম (আপনার গিটহাব অনুযায়ী)
DATASET_FILE = 'email_test.csv'  # আপনার ডাটাসেট ফাইল
MODEL_FILE = 'spam_model.pkl'    # আপনার মডেল ফাইল (GitHub এ যা আছে)
VECTORIZER_FILE = 'vectorizer.pkl'

# --- ২. সেশন স্টেট ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'emails_df' not in st.session_state: st.session_state.emails_df = pd.DataFrame()

# --- ৩. মডেল লোড ---
@st.cache_resource
def load_resources():
    try:
        model = pickle.load(open(MODEL_FILE, 'rb'))
        vectorizer = pickle.load(open(VECTORIZER_FILE, 'rb'))
        return model, vectorizer
    except:
        return None, None

model, vectorizer = load_resources()

# --- ৪. 🔥 রি-ট্রেনিং ফাংশন (সবচেয়ে গুরুত্বপূর্ণ অংশ) ---
def add_data_and_retrain(new_text, label):
    """
    new_text: মেইলের সাবজেক্ট
    label: 1 (Spam) or 0 (Safe)
    """
    try:
        # ১. নতুন ডাটা তৈরি
        # আপনার CSV ফাইলে কলামের নাম যদি 'text' আর 'spam' হয়:
        new_row = pd.DataFrame({'text': [new_text], 'spam': [label]})
        
        # ২. পুরনো CSV ফাইলে নতুন ডাটা যোগ করা (Append)
        # যদি ফাইল না থাকে, নতুন বানাবে। থাকলে শেষে যোগ করবে।
        try:
            pd.read_csv(DATASET_FILE) # চেক করছি ফাইল আছে কিনা
            new_row.to_csv(DATASET_FILE, mode='a', header=False, index=False)
        except FileNotFoundError:
            # ফাইল না থাকলে নতুন করে বানাবে
            new_row.to_csv(DATASET_FILE, index=False)
        
        # ৩. রি-ট্রেনিং (পুরো ফাইল আবার পড়ে মডেল আপডেট করা)
        df = pd.read_csv(DATASET_FILE)
        
        # এখানে নিশ্চিত হতে হবে কলামের নাম ঠিক আছে
        # ধরে নিচ্ছি কলামের নাম 'text' এবং 'spam'
        # যদি আপনার ফাইলে 'Message'/'Category' থাকে, নিচের লাইন দুটি আনকমেন্ট করে ঠিক করে নিন:
        # x_data = df['Message']
        # y_data = df['Category'].apply(lambda x: 1 if x=='spam' else 0)
        
        x_data = df['text']
        y_data = df['spam'] # 1=Spam, 0=Safe

        # ভেক্টরাইজার আপডেট
        v = CountVectorizer()
        X_train = v.fit_transform(x_data)
        
        # মডেল আপডেট
        new_model = MultinomialNB()
        new_model.fit(X_train, y_data)
        
        # ৪. নতুন মডেল সেভ করা
        pickle.dump(new_model, open(MODEL_FILE, 'wb'))
        pickle.dump(v, open(VECTORIZER_FILE, 'wb'))
        
        return True
    except Exception as e:
        st.error(f"Retraining Error: {e}. (Check CSV column names!)")
        return False

# কানেকশন ফাংশন
def connect_to_gmail(user, pwd):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd)
        return mail
    except: return None

# --- ৫. সাইডবার ---
with st.sidebar:
    st.title("🧠 Self-Learning Mode")
    
    if not st.session_state.logged_in:
        user_email = st.text_input("Email")
        user_password = st.text_input("App Password", type="password")
        if st.button("Login"):
            if connect_to_gmail(user_email, user_password):
                st.session_state.logged_in = True
                st.session_state.user_email = user_email
                st.session_state.user_password = user_password
                st.rerun()
    else:
        st.success("Connected ✅")
        folder = st.selectbox("Select Folder", ["INBOX", "[Gmail]/Spam"])
        limit = st.slider("Scan Limit", 10, 100, 30)
        
        if st.button("🔄 Scan Again"):
            st.session_state.emails_df = pd.DataFrame()
            st.rerun()

# --- ৬. মেইন অ্যাপ ---
if st.session_state.logged_in:
    st.header(f"Scanning: {folder}")
    
    # স্ক্যানিং লজিক
    if st.session_state.emails_df.empty:
        with st.spinner("Analyzing emails..."):
            mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
            mail.select(folder)
            _, msgs = mail.uid('search', None, "ALL")
            if msgs[0]:
                uids = msgs[0].split()[-limit:]
                data = []
                for uid in reversed(uids):
                    try:
                        _, data_msg = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                        msg = email.message_from_bytes(data_msg[0][1])
                        subject = decode_header(msg["Subject"])[0][0]
                        if isinstance(subject, bytes): subject = subject.decode()
                        sender = msg.get("From", "")
                        
                        # AI Prediction
                        category = "Unknown"
                        if model:
                            vec = vectorizer.transform([subject])
                            pred = model.predict(vec)[0]
                            category = "Spam" if pred == 1 else "Safe"
                        
                        data.append({"UID": uid, "Subject": subject, "Sender": sender, "Category": category})
                    except: continue
                st.session_state.emails_df = pd.DataFrame(data)
    
    # রেজাল্ট ডিসপ্লে
    if not st.session_state.emails_df.empty:
        df = st.session_state.emails_df
        
        for index, row in df.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([1, 4, 1.5, 1])
                
                # স্ট্যাটাস কালার
                color = "red" if row['Category'] == "Spam" else "green"
                c1.markdown(f":{color}[{row['Category']}]")
                c2.write(f"**{row['Subject']}**\n\n<span style='color:gray; font-size:0.8em'>{row['Sender']}</span>", unsafe_allow_html=True)
                
                # 🔥 TEACHING BUTTONS (মডেলকে শেখানো)
                
                # যদি মডেল ভুল করে Spam বলে, আপনি বলবেন "Mark Safe"
                if row['Category'] == "Spam":
                    if c3.button("✅ Mark Safe & Train", key=f"safe_{row['UID']}"):
                        with st.spinner("Updating dataset & Retraining model..."):
                            # 0 = Safe
                            if add_data_and_retrain(row['Subject'], 0):
                                st.toast("Dataset Updated! Model Retrained successfully.", icon="🎉")
                                time.sleep(1)
                                st.rerun()
                
                # যদি মডেল ভুল করে Safe বলে, আপনি বলবেন "Mark Spam"
                else:
                    if c3.button("🚫 Mark Spam & Train", key=f"spam_{row['UID']}"):
                        with st.spinner("Updating dataset & Retraining model..."):
                            # 1 = Spam
                            if add_data_and_retrain(row['Subject'], 1):
                                st.toast("Dataset Updated! Model Retrained successfully.", icon="🤖")
                                time.sleep(1)
                                st.rerun()

                # ডিলিট বাটন
                if row['Category'] == "Spam":
                    if c4.button("🗑️ Delete", key=f"del_{row['UID']}"):
                        mail = connect_to_gmail(st.session_state.user_email, st.session_state.user_password)
                        mail.select(folder)
                        mail.uid('STORE', row['UID'], '+FLAGS', '\\Deleted')
                        mail.expunge()
                        st.toast("Email Deleted!")
                        time.sleep(1)
                        st.rerun()
                
                st.divider()

else:
    st.warning("Please Login from the sidebar.")
