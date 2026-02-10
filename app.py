import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle
import pandas as pd
import plotly.express as px  # গ্রাফের জন্য

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

# --- মেইন ফাংশন ---
def process_emails(username, password):
    try:
        # ১. জিমেইলে কানেক্ট করা
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, password)
        mail.select("[Gmail]/Spam")

        status, messages = mail.search(None, "ALL")
        mail_ids = messages[0].split()
        
        if not mail_ids:
            st.success("🎉 আপনার ইনবক্স ১০০% ক্লিন! কোনো স্প্যাম নেই।")
            return

        # ২. স্ক্যানিং শুরু
        st.info(f"🔍 স্ক্যান করা হচ্ছে... মোট মেইল: {len(mail_ids)}")
        
        data_list = []
        progress_bar = st.progress(0)
        
        # ==========================================
        # 🔥 সুপার স্ট্রং হোয়াইটলিস্ট (সব কীওয়ার্ড)
        # ==========================================
       # ১. শব্দ (Keywords) - সাবজেক্টে এগুলো থাকলেই সেফ
        whitelist_keywords = [
            # ভার্সিটি ও পড়াশোনা
            "class test", "exam", "quiz", "assignment", "marks", " cgpa ", "final result", # 'grade' বাদ দিয়েছি বা স্পেসিফিক করেছি
            "university", "varsity", "routine", "schedule", "notice", "teacher", 
            "professor", "lecture", "student", "portal", "admission",
            
            # চাকরি ও ক্যারিয়ার
            "interview", "job offer", "hiring", "application", "recruit", 
            "resume", "cv", "shortlist", "appointment", "meeting", 
            
            # টাকা ও ব্যাংক (Finance)
            "bank", "statement", "transaction", "payment", "invoice", 
            "receipt", "otp", "verification", "code", "bkash", "nagad", "rocket",
            
            # অন্যান্য
            "delivery", "order", "reset password", "security alert"
        ]

        # ২. ডোমেইন (Senders) - এদের মেইল কখনোই ডিলিট হবে না
        whitelist_senders = [
            ".edu", ".ac.bd", ".gov", ".org", 
            "google.com", "linkedin.com", "facebook.com", "udacity.com",
            "coursera.org", "medium.com", "zoom.us", "microsoft.com",
            "streamlit.io", "github.com", "kaggle.com"  # <--- এইগুলো নতুন যোগ করুন
        ]
        for i, e_id in enumerate(mail_ids):
            try:
                res, msg = mail.fetch(e_id, "(RFC822)")
                for response in msg:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        
                        # সাবজেক্ট ডিকোড
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        sender = msg.get("From", "").lower()
                        subject_lower = subject.lower()
                        
                        # --- ডিসিশন লজিক ---
                        category = "Spam"  # ডিফল্টভাবে স্প্যাম ধরব
                        reason = "Unknown"
                        is_safe = False

                        # ১. সেন্ডার চেক
                        for s in whitelist_senders:
                            if s in sender:
                                is_safe = True
                                reason = f"Trusted Sender ({s})"
                                break

                        # ২. কীওয়ার্ড চেক (যদি সেন্ডার সেফ না হয়)
                        if not is_safe:
                            for w in whitelist_keywords:
                                if w in subject_lower:
                                    is_safe = True
                                    reason = f"Keyword: '{w}'"
                                    break
                        
                        # ৩. AI মডেল চেক (যদি উপরের দুটোতে ধরা না পড়ে)
                        if not is_safe and model:
                            try:
                                vec = vectorizer.transform([subject])
                                if model.predict(vec)[0] == 0:  # 0 = Ham
                                    is_safe = True
                                    reason = "AI Model (Safe)"
                            except:
                                pass # এরর হলে রিস্ক নেব না

                        # ফাইনাল ক্যাটাগরি সেট করা
                        if is_safe:
                            category = "Safe"
                        else:
                            reason = "High Risk Spam"

                        data_list.append({
                            "ID": e_id,
                            "Subject": subject,
                            "Sender": sender,
                            "Category": category,
                            "Reason": reason,
                            "Select": True if category == "Spam" else False # শুধু স্প্যামগুলো অটো-সিলেক্ট হবে
                        })
            
            except Exception as e:
                continue
            
            progress_bar.progress((i + 1) / len(mail_ids))

        # --- ৩. ড্যাশবোর্ড (Dashboard Visualization) 📊 ---
        df = pd.DataFrame(data_list)
        
        if not df.empty:
            st.markdown("### 📊 Inbox Health Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Emails Scanned", len(df))
            col2.metric("Safe Emails 🛡️", len(df[df['Category']=='Safe']))
            col3.metric("Spam Emails 🚨", len(df[df['Category']=='Spam']), delta_color="inverse")

            # পাই চার্ট
            fig = px.pie(df, names='Category', title='Spam vs Safe Ratio', 
                         color='Category', color_discrete_map={'Safe':'#2ecc71', 'Spam':'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # --- ৪. অ্যাকশন সেন্টার (User Control Table) ✅ ---
            st.subheader("🛠️ Action Center")
            st.markdown("নিচে চিহ্নিত মেইলগুলো **ডিলিট** করা হবে। আপনি চাইলে টিক মার্ক তুলে সেভ করতে পারেন।")
            
            edited_df = st.data_editor(
                df[['Select', 'Category', 'Subject', 'Reason', 'Sender']],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Delete?", help="Check to delete", default=False),
                    "Category": st.column_config.TextColumn("Status", width="small"),
                    "Subject": st.column_config.TextColumn("Subject", width="large"),
                    "Sender": st.column_config.TextColumn("Sender", width="medium"),
                },
                disabled=["Category", "Subject", "Reason", "Sender"], # শুধু চেকবক্স এডিট করা যাবে
                hide_index=True,
                use_container_width=True
            )

            # ডিলিট বাটন
            to_delete = edited_df[edited_df['Select'] == True]
            
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("🗑️ Delete Selected", type="primary"):
                    if not to_delete.empty:
                        with st.spinner("Deleting selected emails..."):
                            # আসল আইডি বের করে ডিলিট করা
                            original_ids = df.loc[to_delete.index, 'ID'].tolist()
                            
                            for mail_id in original_ids:
                                mail.store(mail_id, "+FLAGS", "\\Deleted")
                            
                            mail.expunge()
                            st.balloons()
                            st.success(f"Successfully deleted {len(to_delete)} emails!")
                            st.rerun()
                    else:
                        st.warning("No emails selected for deletion.")

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

