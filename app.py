import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px

# পেজ কনফিগারেশন
st.set_page_config(page_title="AI Spam Cleaner Pro", page_icon="🧹", layout="wide")

# --- সাইডবার ---
with st.sidebar:
    st.title("🔐 Login Panel")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    st.divider()
    st.info("Note: Use your Google App Password, not your regular Gmail password.")
    st.caption("Developed by Toufique Ahmed")

# --- মডেল লোড ---
@st.cache_resource
def load_models():
    try:
        model = pickle.load(open('model.pkl', 'rb'))
        vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
        return model, vectorizer
    except:
        return None, None

model, vectorizer = load_models()

# --- মেইন ফাংশন (UID ফিক্সড) ---
def process_emails(username, password):
    try:
        # ১. কানেকশন
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        mail.select("[Gmail]/Spam")

        # ২. স্ক্যানিং (UID ব্যবহার করে) 🔥 গুরুত্ত্বপূর্ণ পরিবর্তন
        status, messages = mail.uid('search', None, "ALL")
        
        if messages[0]:
            mail_ids = messages[0].split()
        else:
            st.success("🎉 আপনার ইনবক্স ১০০% ক্লিন! কোনো স্প্যাম নেই।")
            return

        st.info(f"🔍 স্ক্যান করা হচ্ছে... মোট মেইল: {len(mail_ids)}")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # আপনার হোয়াইটলিস্ট
        whitelist_keywords = [
            "class", "exam", "quiz", "assignment", "marks", "result", "grade", 
            "university", "varsity", "routine", "schedule", "notice", "teacher", 
            "professor", "lecture", "student", "portal", "fee", "admission",
            "interview", "offer", "job", "hiring", "application", "recruit", 
            "resume", "cv", "selection", "shortlist", "appointment", "meeting", 
            "bank", "statement", "transaction", "payment", "bill", "invoice", 
            "receipt", "otp", "verification", "code", "bkash", "nagad", "rocket",
            "order", "placed", "shipped", "delivery", "courier", "password", 
            "reset", "login", "security", "alert", "verify"
        ]

        whitelist_senders = [
            ".edu", ".ac.bd", ".gov", ".org", "google.com", "linkedin.com", 
            "facebook.com", "udacity.com", "coursera.org", "medium.com", 
            "zoom.us", "microsoft.com", "github.com", "kaggle.com", "streamlit.io"
        ]

        # উল্টো দিক থেকে লুপ চালানো ভালো (Latest mail first)
        for i, e_id in enumerate(reversed(mail_ids)):
            try:
                # UID দিয়ে মেইল পড়া 🔥
                res, msg = mail.uid('fetch', e_id, "(RFC822)")
                for response in msg:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        sender = msg.get("From", "").lower()
                        subject_lower = subject.lower()
                        
                        # --- লজিক ---
                        category = "Spam"
                        reason = "Unknown"
                        is_safe = False

                        for s in whitelist_senders:
                            if s in sender:
                                is_safe = True
                                reason = f"Trusted Sender ({s})"
                                break

                        if not is_safe:
                            for w in whitelist_keywords:
                                if w in subject_lower:
                                    is_safe = True
                                    reason = f"Keyword: '{w}'"
                                    break
                        
                        if not is_safe and model:
                            try:
                                vec = vectorizer.transform([subject])
                                if model.predict(vec)[0] == 0:
                                    is_safe = True
                                    reason = "AI Model (Safe)"
                            except:
                                pass

                        if is_safe:
                            category = "Safe"
                        else:
                            reason = "High Risk Spam"

                        data_list.append({
                            "ID": e_id, # এখন এটি পার্মানেন্ট UID
                            "Subject": subject,
                            "Sender": sender,
                            "Category": category,
                            "Reason": reason,
                            "Select": True if category == "Spam" else False
                        })
            
            except Exception as e:
                continue
            
            progress_bar.progress((i + 1) / len(mail_ids))

        # --- ৩. ড্যাশবোর্ড ও অ্যাকশন ---
        df = pd.DataFrame(data_list)
        
        if not df.empty:
            st.markdown("### 📊 Inbox Health Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Emails", len(df))
            col2.metric("Safe", len(df[df['Category']=='Safe']))
            col3.metric("Spam", len(df[df['Category']=='Spam']), delta_color="inverse")
            
            fig = px.pie(df, names='Category', title='Spam vs Safe Ratio', 
                         color='Category', color_discrete_map={'Safe':'#2ecc71', 'Spam':'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)

            st.divider()

            st.subheader("🛠️ Action Center")
            
            edited_df = st.data_editor(
                df[['Select', 'Category', 'Subject', 'Reason', 'Sender']],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Delete?", default=False),
                },
                disabled=["Category", "Subject", "Reason", "Sender"],
                hide_index=True,
                use_container_width=True
            )

            to_delete = edited_df[edited_df['Select'] == True]
            
            if st.button("🗑️ Delete Selected", type="primary"):
                if not to_delete.empty:
                    with st.spinner("Deleting selected emails permanently..."):
                        # আসল UID বের করে ডিলিট করা 🔥
                        original_uids = df.loc[to_delete.index, 'ID'].tolist()
                        
                        for uid in original_uids:
                            # UID দিয়ে ডিলিট মার্ক করা 🔥
                            mail.uid('store', uid, "+FLAGS", "\\Deleted")
                        
                        # পার্মানেন্টলি ডিলিট
                        mail.expunge()
                        st.balloons()
                        st.success(f"Successfully deleted {len(to_delete)} emails!")
                        st.rerun()
                else:
                    st.warning("No emails selected.")

        mail.logout()

    except Exception as e:
        st.error(f"Error: {e}")

# --- রান ---
st.title("🚀 AI Spam Cleaner Pro")
if user_email and user_password:
    if st.button("🚀 Start Scan"):
        process_emails(user_email, user_password)
else:
    st.info("👈 Please login from the sidebar to start scanning.")
