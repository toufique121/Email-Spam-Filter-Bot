import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px

# 1. পেজ সেটআপ
st.set_page_config(page_title="AI Spam Cleaner Pro", page_icon="🧹", layout="wide")

# 2. সাইডবার
with st.sidebar:
    st.title("🔐 Login Panel")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    st.divider()
    
    st.subheader("⚙️ Settings")
    target_folder = st.selectbox("Select Folder:", ["[Gmail]/Spam", "INBOX"])
    email_limit = st.slider("Scan Limit:", 10, 200, 50)
    
    # 🔥 ট্র্যাশ খালি করার বাটন (আলাদা করে)
    if st.button("💀 Force Empty Trash/Bin"):
        if user_email and user_password:
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(user_email, user_password)
                
                # ট্র্যাশ ফোল্ডার ডিটেক্ট করা
                trash_list = ["[Gmail]/Trash", "[Gmail]/Bin", "Trash", "Bin"]
                found_trash = None
                
                for t in trash_list:
                    try:
                        status, _ = mail.select(t)
                        if status == 'OK':
                            found_trash = t
                            break
                    except:
                        continue
                
                if found_trash:
                    mail.store("1:*", "+FLAGS", "\\Deleted")
                    mail.expunge()
                    st.success(f"💥 {found_trash} has been emptied!")
                else:
                    st.error("Could not find Trash folder!")
                mail.logout()
            except Exception as e:
                st.error(f"Error: {e}")

# 3. মডেল লোড
@st.cache_resource
def load_models():
    try:
        model = pickle.load(open('model.pkl', 'rb'))
        vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
        return model, vectorizer
    except:
        return None, None

model, vectorizer = load_models()

# 4. মেইন প্রসেসিং ফাংশন
def process_emails(username, password, folder, limit):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        
        # ১. আগে ট্র্যাশ ফোল্ডারের নাম খুঁজে বের করি
        trash_folder_name = "[Gmail]/Trash"
        try:
            mail.select("[Gmail]/Trash")
        except:
            trash_folder_name = "[Gmail]/Bin"
        
        # ২. টার্গেট ফোল্ডার সিলেক্ট
        status, _ = mail.select(folder)
        if status != 'OK':
            st.error(f"Cannot open {folder}")
            return

        status, messages = mail.uid('search', None, "ALL")
        if not messages[0]:
            st.success(f"🎉 {folder} is empty!")
            return

        all_ids = messages[0].split()
        latest_ids = all_ids[-limit:]

        st.info(f"🔍 Scanning {len(latest_ids)} emails in {folder}...")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # হোয়াইটলিস্ট
        whitelist_senders = ["google.com", "linkedin.com", "facebook.com", "upwork.com", ".edu", ".gov", "streamlit.io", "github.com"]
        whitelist_keywords = ["job", "interview", "offer", "class", "exam", "grade", "university", "bkash", "nagad", "otp", "verify"]

        for i, e_id in enumerate(reversed(latest_ids)):
            try:
                res, msg = mail.uid('fetch', e_id, "(RFC822)")
                for response in msg:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        sender = msg.get("From", "").lower()
                        
                        # ক্যাটাগরি লজিক
                        category = "Safe" if folder == "INBOX" else "Spam"
                        reason = "Unknown"
                        
                        # 1. Whitelist Check
                        is_safe = False
                        for s in whitelist_senders:
                            if s in sender: 
                                is_safe = True; category = "Safe"; reason = "Trusted Sender"; break
                        
                        if not is_safe:
                            for w in whitelist_keywords:
                                if w in subject.lower():
                                    is_safe = True; category = "Safe"; reason = "Keyword Match"; break
                        
                        # 2. AI Check (Only if not safe yet)
                        if not is_safe and model:
                            try:
                                vec = vectorizer.transform([subject])
                                if model.predict(vec)[0] == 1:
                                    category = "Spam"; reason = "AI Detected Spam"
                            except: pass

                        data_list.append({
                            "ID": e_id, "Subject": subject, "Sender": sender,
                            "Category": category, "Reason": reason,
                            "Select": True if category == "Spam" else False
                        })
            except: continue
            progress_bar.progress((i + 1) / len(latest_ids))

        # রেজাল্ট টেবিল
        df = pd.DataFrame(data_list)
        if not df.empty:
            st.subheader("🛠️ Action Center")
            edited_df = st.data_editor(
                df[['Select', 'Category', 'Subject', 'Sender']],
                column_config={"Select": st.column_config.CheckboxColumn("Delete?", default=False)},
                disabled=["Category", "Subject", "Sender"],
                hide_index=True, use_container_width=True
            )

            to_delete = edited_df[edited_df['Select'] == True]
            
            # 🔥 POWERFUL DELETE BUTTON 🔥
            if st.button("🗑️ Move Selected to Trash"):
                if not to_delete.empty:
                    with st.spinner("Moving emails to Trash..."):
                        uids = df.loc[to_delete.index, 'ID'].tolist()
                        count = 0
                        
                        for uid in uids:
                            try:
                                # 1. Copy to Trash
                                result = mail.uid('COPY', uid, trash_folder_name)
                                if result[0] == 'OK':
                                    # 2. Mark Deleted in Current Folder
                                    mail.uid('STORE', uid, '+FLAGS', '(\\Deleted)')
                                    count += 1
                            except Exception as e:
                                print(e)
                        
                        # 3. Expunge Current Folder
                        mail.expunge()
                        st.success(f"Moved {count} emails to {trash_folder_name}!")
                        st.info("Now click 'Force Empty Trash' in sidebar to delete permanently.")
                        st.rerun()

        mail.logout()

    except Exception as e:
        st.error(f"Connection Error: {e}")

# রান
if user_email and user_password:
    if st.button("🚀 Start Scan"):
        process_emails(user_email, user_password, target_folder, email_limit)
else:
    st.warning("Login first!")
