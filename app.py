import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px

# 1. পেজ কনফিগারেশন
st.set_page_config(page_title="AI Spam Cleaner Pro", page_icon="🧹", layout="wide")

# 2. সাইডবার (লগইন এবং ফোল্ডার সিলেকশন)
with st.sidebar:
    st.title("🔐 Login Panel")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    
    st.divider()
    
    # 🔥 ফোল্ডার সিলেক্ট করার অপশন (নতুন) 🔥
    st.subheader("⚙️ Scan Settings")
    target_folder = st.selectbox(
        "Select Folder to Clean:",
        ["[Gmail]/Spam", "INBOX"]
    )
    
    # ইনবক্স বিশাল হতে পারে, তাই লিমিট সেট করার অপশন
    email_limit = st.slider("Number of emails to scan:", min_value=10, max_value=200, value=50)

    st.info("⚠️ 'INBOX' সিলেক্ট করলে আপনার মেইন মেইল স্ক্যান হবে। ডিলিট করার আগে সাবধানে চেক করবেন!")
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

# 4. প্রসেসিং ফাংশন
def process_emails(username, password, folder, limit):
    try:
        # কানেকশন
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        
        # Trash ফোল্ডার ডিটেক্ট করা
        trash_folder = "[Gmail]/Trash"
        try:
            mail.select(trash_folder)
        except:
            trash_folder = "[Gmail]/Bin"
        
        # 🔥 ইউজারের সিলেক্ট করা ফোল্ডার ওপেন করা 🔥
        try:
            status, response = mail.select(folder)
            if status != 'OK':
                st.error(f"❌ ফোল্ডার '{folder}' ওপেন করা যাচ্ছে না।")
                return
        except:
            st.error("Error opening folder.")
            return

        # স্ক্যানিং (UID Search)
        status, messages = mail.uid('search', None, "ALL")
        
        if not messages[0]:
            st.success(f"🎉 '{folder}' ফোল্ডার একদম ফাঁকা!")
            return

        # সব মেইল না নিয়ে, শেষের (Latest) কিছু মেইল নেওয়া
        all_ids = messages[0].split()
        latest_ids = all_ids[-limit:] # স্লাইডার দিয়ে ঠিক করা লিমিট অনুযায়ী

        st.info(f"🔍 '{folder}' ফোল্ডারের সর্বশেষ **{len(latest_ids)}** টি মেইল স্ক্যান করা হচ্ছে...")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # হোয়াইটলিস্ট (সেফটি)
        whitelist_keywords = [
            "class", "exam", "quiz", "assignment", "marks", "result", "grade", 
            "university", "varsity", "routine", "schedule", "notice", "teacher", 
            "professor", "lecture", "student", "portal", "fee", "admission",
            "interview", "offer", "job", "hiring", "application", "recruit", 
            "resume", "cv", "selection", "shortlist", "appointment", "meeting", 
            "bank", "statement", "transaction", "payment", "bill", "invoice", 
            "receipt", "otp", "verification", "code", "bkash", "nagad", "rocket",
            "order", "placed", "shipped", "delivery", "courier", "password", 
            "reset", "login", "security", "alert", "verify", "otp"
        ]

        whitelist_senders = [
            ".edu", ".ac.bd", ".gov", ".org", "google.com", "linkedin.com", 
            "facebook.com", "udacity.com", "coursera.org", "medium.com", 
            "zoom.us", "microsoft.com", "github.com", "kaggle.com", "streamlit.io"
        ]

        # লুপ (Reversed = নতুন মেইল আগে)
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
                        
                        # --- লজিক ---
                        # যদি ইনবক্স স্ক্যান করি, ডিফল্ট হবে "Safe", মডেল যদি স্প্যাম বলে তবেই "Spam"
                        # যদি স্প্যাম ফোল্ডার স্ক্যান করি, ডিফল্ট "Spam"
                        
                        if folder == "INBOX":
                             category = "Safe" # ইনবক্সে আমরা ধরে নেব সব মেইল ভালো
                             reason = "Regular Mail"
                             should_check_ai = True
                        else:
                             category = "Spam"
                             reason = "Unknown"
                             should_check_ai = True

                        is_whitelisted = False

                        # ১. হোয়াইটলিস্ট চেক
                        for s in whitelist_senders:
                            if s in sender:
                                is_whitelisted = True
                                category = "Safe"
                                reason = f"Trusted Sender ({s})"
                                should_check_ai = False
                                break

                        if not is_whitelisted:
                            for w in whitelist_keywords:
                                if w in subject_lower:
                                    is_whitelisted = True
                                    category = "Safe"
                                    reason = f"Keyword: '{w}'"
                                    should_check_ai = False
                                    break
                        
                        # ২. AI চেক (শুধুমাত্র যদি হোয়াইটলিস্টে না থাকে)
                        if should_check_ai and model:
                            try:
                                vec = vectorizer.transform([subject])
                                prediction = model.predict(vec)[0]
                                
                                if prediction == 1: # মডেল বলছে SPAM
                                    category = "Spam"
                                    reason = "AI Model Detected Spam"
                                elif prediction == 0 and folder == "[Gmail]/Spam":
                                    # স্প্যাম ফোল্ডারে ছিল কিন্তু মডেল বলছে ভালো
                                    category = "Safe"
                                    reason = "AI Model marked as Safe"
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

        # --- ৩. রেজাল্ট এবং অ্যাকশন ---
        df = pd.DataFrame(data_list)
        
        if not df.empty:
            # Stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Scanned", len(df))
            col2.metric("Safe Emails", len(df[df['Category']=='Safe']))
            col3.metric("Spam Found", len(df[df['Category']=='Spam']), delta_color="inverse")
            
            # Chart
            fig = px.pie(df, names='Category', title=f'Status of scanned emails in {folder}', 
                         color='Category', color_discrete_map={'Safe':'#2ecc71', 'Spam':'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            
            # Table
            st.subheader("🛠️ Action Center")
            edited_df = st.data_editor(
                df[['Select', 'Category', 'Subject', 'Reason', 'Sender']],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Delete?", default=False),
                    "Subject": st.column_config.TextColumn("Subject", width="large"),
                },
                disabled=["Category", "Subject", "Reason", "Sender"],
                hide_index=True,
                use_container_width=True
            )

            # Delete Logic
            to_delete = edited_df[edited_df['Select'] == True]
            
            if st.button("🗑️ Delete Selected", type="primary"):
                if not to_delete.empty:
                    st.toast(f"Moving {len(to_delete)} emails to Trash...")
                    progress_del = st.progress(0)
                    
                    original_uids = df.loc[to_delete.index, 'ID'].tolist()
                    
                    count = 0
                    for idx, uid in enumerate(original_uids):
                        try:
                            mail.uid('COPY', uid, trash_folder)
                            mail.uid('STORE', uid, '+FLAGS', '(\\Deleted)')
                            count += 1
                        except Exception as e:
                            print(e)
                        progress_del.progress((idx + 1) / len(original_uids))
                    
                    mail.expunge()
                    st.balloons()
                    st.success(f"Moved {count} emails to Trash from {folder}!")
                    st.rerun()
                else:
                    st.warning("No emails selected.")

        mail.logout()

    except Exception as e:
        st.error(f"Error: {e}")

# 5. Run App
st.title("🚀 AI Spam Cleaner Pro")

if user_email and user_password:
    # বাটন চাপলে প্রসেস শুরু হবে
    if st.button("🚀 Start Scan"):
        # সাইডবারের সিলেকশন অনুযায়ী ফাংশন কল করা হচ্ছে
        process_emails(user_email, user_password, target_folder, email_limit)
else:
    st.info("👈 Please login from the sidebar.")
