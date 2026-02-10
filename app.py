import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px

# 1. পেজ কনফিগারেশন
st.set_page_config(page_title="AI Spam Cleaner Pro", page_icon="🧹", layout="wide")

# 2. সাইডবার (লগইন প্যানেল)
with st.sidebar:
    st.title("🔐 Login Panel")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    st.divider()
    st.info("⚠️ Note: Use your Google App Password, NOT your regular Gmail password.")
    st.caption("Developed by Toufique Ahmed")

# 3. মডেল লোড করা (ক্যাশ মেমোরি সহ)
@st.cache_resource
def load_models():
    try:
        model = pickle.load(open('model.pkl', 'rb'))
        vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
        return model, vectorizer
    except:
        return None, None

model, vectorizer = load_models()

# 4. মেইল প্রসেসিং এবং ক্লিনিং ফাংশন
def process_emails(username, password):
    try:
        # --- কানেকশন তৈরি ---
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        
        # Trash ফোল্ডার খুঁজে বের করা (Trash নাকি Bin?)
        # জিমেইলে জায়গাভেদে নাম আলাদা হয়, তাই এটা অটো চেক করবে।
        trash_folder = "[Gmail]/Trash"
        try:
            mail.select(trash_folder)
        except:
            trash_folder = "[Gmail]/Bin"
        
        # স্প্যাম ফোল্ডার সিলেক্ট করা
        mail.select("[Gmail]/Spam")

        # --- স্ক্যানিং (UID ব্যবহার করে) ---
        # সাধারণ search এর বদলে uid search ব্যবহার করা হয়েছে যাতে ভুল মেইল ডিলিট না হয়
        status, messages = mail.uid('search', None, "ALL")
        
        if messages[0]:
            mail_ids = messages[0].split()
        else:
            st.success("🎉 আপনার ইনবক্স ১০০% ক্লিন! কোনো স্প্যাম নেই।")
            mail.logout()
            return

        st.info(f"🔍 স্ক্যান করা হচ্ছে... মোট মেইল: {len(mail_ids)}")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # --- হোয়াইটলিস্ট (Whitelist) ---
        whitelist_keywords = [
            # ভার্সিটি ও পড়াশোনা
            "class", "exam", "quiz", "assignment", "marks", "result", "grade", 
            "university", "varsity", "routine", "schedule", "notice", "teacher", 
            "professor", "lecture", "student", "portal", "fee", "admission",
            # চাকরি ও ক্যারিয়ার
            "interview", "offer", "job", "hiring", "application", "recruit", 
            "resume", "cv", "selection", "shortlist", "appointment", "meeting", 
            # টাকা ও ব্যাংক
            "bank", "statement", "transaction", "payment", "bill", "invoice", 
            "receipt", "otp", "verification", "code", "bkash", "nagad", "rocket",
            # অন্যান্য
            "order", "placed", "shipped", "delivery", "courier", "password", 
            "reset", "login", "security", "alert", "verify"
        ]

        whitelist_senders = [
            ".edu", ".ac.bd", ".gov", ".org", "google.com", "linkedin.com", 
            "facebook.com", "udacity.com", "coursera.org", "medium.com", 
            "zoom.us", "microsoft.com", "github.com", "kaggle.com", "streamlit.io"
        ]

        # উল্টো দিক থেকে লুপ (নতুন মেইল আগে দেখাবে)
        for i, e_id in enumerate(reversed(mail_ids)):
            try:
                # UID দিয়ে মেইল পড়া
                res, msg = mail.uid('fetch', e_id, "(RFC822)")
                for response in msg:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        
                        # সাবজেক্ট ডিকোড করা
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        sender = msg.get("From", "").lower()
                        subject_lower = subject.lower()
                        
                        # --- লজিক (AI + Rules) ---
                        category = "Spam"
                        reason = "Unknown"
                        is_safe = False

                        # ১. সেন্ডার চেক
                        for s in whitelist_senders:
                            if s in sender:
                                is_safe = True
                                reason = f"Trusted Sender ({s})"
                                break
                        
                        # ২. কিওয়ার্ড চেক
                        if not is_safe:
                            for w in whitelist_keywords:
                                if w in subject_lower:
                                    is_safe = True
                                    reason = f"Keyword: '{w}'"
                                    break
                        
                        # ৩. AI মডেল চেক
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
                            "ID": e_id,  # এটি UID
                            "Subject": subject,
                            "Sender": sender,
                            "Category": category,
                            "Reason": reason,
                            "Select": True if category == "Spam" else False
                        })
            
            except Exception as e:
                continue # রিড করতে না পারলে স্কিপ করবে
            
            progress_bar.progress((i + 1) / len(mail_ids))

        # --- ৩. ড্যাশবোর্ড ও অ্যাকশন ---
        df = pd.DataFrame(data_list)
        
        if not df.empty:
            st.markdown("### 📊 Inbox Health Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Emails", len(df))
            col2.metric("Safe", len(df[df['Category']=='Safe']))
            col3.metric("Spam", len(df[df['Category']=='Spam']), delta_color="inverse")
            
            # পাই চার্ট
            fig = px.pie(df, names='Category', title='Spam vs Safe Ratio', 
                         color='Category', color_discrete_map={'Safe':'#2ecc71', 'Spam':'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # অ্যাকশন সেন্টার (চেকবক্স)
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

            # সিলেক্ট করা মেইলগুলো আলাদা করা
            to_delete = edited_df[edited_df['Select'] == True]
            
            # 🔥 ডিলিট বাটন (Move to Trash মেথড) 🔥
            if st.button("🗑️ Delete Selected", type="primary"):
                if not to_delete.empty:
                    status_text = st.empty()
                    status_text.info(f"Moving {len(to_delete)} emails to Trash/Bin...")
                    
                    progress_del = st.progress(0)
                    
                    # আসল UID লিস্ট
                    original_uids = df.loc[to_delete.index, 'ID'].tolist()
                    
                    count = 0
                    for idx, uid in enumerate(original_uids):
                        try:
                            # ১. ট্র্যাশ ফোল্ডারে কপি করা (Move)
                            mail.uid('COPY', uid, trash_folder)
                            # ২. স্প্যাম ফোল্ডার থেকে ডিলিট মার্ক করা
                            mail.uid('STORE', uid, '+FLAGS', '(\\Deleted)')
                            count += 1
                        except Exception as e:
                            print(f"Error: {e}")
                        
                        progress_del.progress((idx + 1) / len(original_uids))
                    
                    # ৩. পার্মানেন্ট রিমুভ (Expunge)
                    mail.expunge()
                    
                    st.balloons()
                    status_text.success(f"✅ সফলভাবে {count} টি মেইল Trash ফোল্ডারে পাঠানো হয়েছে!")
                    
                    # পেজ রিফ্রেশ (যাতে লিস্ট আপডেট হয়)
                    st.rerun()
                else:
                    st.warning("⚠️ No emails selected for deletion.")

        mail.logout()

    except Exception as e:
        st.error(f"Error: {e}")

# 5. অ্যাপ রান করা
st.title("🚀 AI Spam Cleaner Pro")

if user_email and user_password:
    if st.button("🚀 Start Scan"):
        process_emails(user_email, user_password)
else:
    st.info("👈 Please login from the sidebar to start scanning.")
