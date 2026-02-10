import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px

# 1. পেজ কনফিগারেশন
st.set_page_config(page_title="AI Spam Cleaner Pro", page_icon="🧹", layout="wide")

# 2. সাইডবার
with st.sidebar:
    st.title("🔐 Login Panel")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    st.divider()
    
    # সেটিংস
    st.subheader("⚙️ Scan Settings")
    target_folder = st.selectbox("Select Folder:", ["[Gmail]/Spam", "INBOX"])
    email_limit = st.slider("Scan Limit:", 10, 200, 50)
    
    st.caption("Developed by Toufique Ahmed")

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

# 4. প্রসেসিং ফাংশন (সিম্পল ডিলিট লজিক)
def process_emails(username, password, folder, limit):
    try:
        # কানেকশন
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        
        # ফোল্ডার ওপেন করা
        status, response = mail.select(folder)
        if status != 'OK':
            st.error(f"❌ '{folder}' ওপেন করা যাচ্ছে না।")
            return

        # স্ক্যানিং (UID)
        status, messages = mail.uid('search', None, "ALL")
        if not messages[0]:
            st.success(f"🎉 '{folder}' ফোল্ডার একদম ফাঁকা!")
            return

        all_ids = messages[0].split()
        latest_ids = all_ids[-limit:]

        st.info(f"🔍 স্ক্যান করা হচ্ছে... ({len(latest_ids)} emails)")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # হোয়াইটলিস্ট
        whitelist_keywords = ["class", "exam", "quiz", "result", "grade", "university", "interview", "offer", "job", "bkash", "nagad", "otp", "code", "login", "alert"]
        whitelist_senders = [".edu", "google.com", "linkedin.com", "facebook.com", "udacity.com", "github.com", "streamlit.io"]

        # লুপ
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
                        subject_lower = subject.lower()
                        
                        # লজিক
                        if folder == "INBOX":
                             category = "Safe"
                             reason = "Regular Mail"
                             should_check_ai = True
                        else:
                             category = "Spam"
                             reason = "Unknown"
                             should_check_ai = True

                        is_whitelisted = False
                        for s in whitelist_senders:
                            if s in sender:
                                is_whitelisted = True
                                category = "Safe"
                                reason = "Trusted Sender"
                                should_check_ai = False
                                break
                        
                        if not is_whitelisted:
                            for w in whitelist_keywords:
                                if w in subject_lower:
                                    is_whitelisted = True
                                    category = "Safe"
                                    reason = f"Keyword: {w}"
                                    should_check_ai = False
                                    break
                        
                        if should_check_ai and model:
                            try:
                                vec = vectorizer.transform([subject])
                                if model.predict(vec)[0] == 1:
                                    category = "Spam"
                                    reason = "AI Detected Spam"
                            except:
                                pass

                        data_list.append({
                            "ID": e_id, 
                            "Subject": subject,
                            "Sender": sender,
                            "Category": category,
                            "Reason": reason,
                            "Select": True if category == "Spam" else False
                        })
            except:
                continue
            progress_bar.progress((i + 1) / len(latest_ids))

        # রেজাল্ট
        df = pd.DataFrame(data_list)
        if not df.empty:
            # চার্ট
            col1, col2 = st.columns(2)
            col1.metric("Total Emails", len(df))
            col2.metric("Spam Found", len(df[df['Category']=='Spam']), delta_color="inverse")
            
            fig = px.pie(df, names='Category', title=f'{folder} Overview', color='Category', color_discrete_map={'Safe':'#2ecc71', 'Spam':'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)

            # অ্যাকশন সেন্টার
            st.subheader("🛠️ Action Center")
            edited_df = st.data_editor(
                df[['Select', 'Category', 'Subject', 'Reason', 'Sender']],
                column_config={"Select": st.column_config.CheckboxColumn("Delete?", default=False)},
                disabled=["Category", "Subject", "Reason", "Sender"],
                hide_index=True,
                use_container_width=True
            )

            to_delete = edited_df[edited_df['Select'] == True]
            
            # 🔥🔥🔥 FORCE DELETE BUTTON 🔥🔥🔥
            if st.button("🗑️ Delete Selected Emails"):
                if not to_delete.empty:
                    # স্পিনার যোগ করা যাতে ইউজার বোঝে কাজ হচ্ছে
                    with st.spinner("Deleting emails permanently..."):
                        
                        original_uids = df.loc[to_delete.index, 'ID'].tolist()
                        
                        count = 0
                        for uid in original_uids:
                            try:
                                # সরাসরি ডিলিট ফ্ল্যাগ বসানো (Trash এ কপি না করেই)
                                mail.uid('STORE', uid, '+FLAGS', '\\Deleted')
                                count += 1
                            except Exception as e:
                                st.error(f"Error deleting ID {uid}: {e}")
                        
                        # ধাক্কা দিয়ে বের করে দেওয়া (Expunge)
                        mail.expunge()
                        
                        st.balloons()
                        st.success(f"🚀 {count} emails deleted successfully from {folder}!")
                        
                        # লিস্ট রিফ্রেশ করার জন্য রিরান
                        st.rerun()
                else:
                    st.warning("No emails selected.")

        mail.logout()

    except Exception as e:
        st.error(f"Error: {e}")

# 5. অ্যাপ রান
st.title("🚀 AI Spam Cleaner Pro")
if user_email and user_password:
    if st.button("🚀 Start Scan"):
        process_emails(user_email, user_password, target_folder, email_limit)
else:
    st.info("Please login first.")
