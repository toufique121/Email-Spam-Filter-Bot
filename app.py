import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib

# ==========================================
# ১. পেজ সেটআপ এবং ডিজাইন
# ==========================================
st.set_page_config(page_title="AI Spam Cleaner", page_icon="📧")

st.title("📧 AI Email Spam Cleaner")
st.write("এই টুলটি আপনার জিমেইল চেক করে **Spam** মেইল খুঁজে বের করবে এবং ডিলিট করার অপশন দেবে।")

# সাইডবার (নির্দেশনা)
with st.sidebar:
    st.header("⚠️ ব্যবহারের নিয়ম")
    st.write("""
    ১. আপনার জিমেইলের **2-Step Verification** অন থাকতে হবে।
    2. সাধারণ পাসওয়ার্ড কাজ করবে না। আপনাকে **App Password** তৈরি করতে হবে।
    3. [কিভাবে App Password পাবেন?](https://support.google.com/accounts/answer/185833)
    """)
    st.warning("আমরা আপনার পাসওয়ার্ড সেভ করি না। এটি সরাসরি Google এর সাথে কানেক্ট হয়।")

# ==========================================
# ২. ইউজার ইনপুট (সবার জন্য)
# ==========================================
email_user = st.text_input("আপনার জিমেইল (Gmail):", placeholder="example@gmail.com")
email_pass = st.text_input("আপনার অ্যাপ পাসওয়ার্ড (App Password):", type="password", placeholder="16 digit app password")

# ==========================================
# ৩. মডেল লোড করা
# ==========================================
try:
    model = joblib.load('spam_model.pkl')
    cv = joblib.load('vectorizer.pkl')
except FileNotFoundError:
    st.error("মডেল ফাইল পাওয়া যায়নি! দয়া করে 'spam_model.pkl' আপলোড করুন।")

# ==========================================
# ৪. মেইন ফাংশন
# ==========================================
if st.button("🚀 মেইল চেক করুন"):
    if not email_user or not email_pass:
        st.warning("দয়া করে ইমেইল এবং পাসওয়ার্ড দিন।")
    else:
        status_area = st.empty()
        status_area.info("🔗 জিমেইলে কানেক্ট করা হচ্ছে...")
        
        try:
            # সার্ভারে কানেক্ট করা
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_user, email_pass)
            mail.select("inbox")

            # মেইল খোঁজা
            status, messages = mail.search(None, 'UNSEEN')
            mail_ids = messages[0].split()

            if not mail_ids:
                status_area.success("📭 কোনো নতুন (Unseen) মেইল নেই। সব ক্লিয়ার!")
            else:
                status_area.write(f"🔍 **{len(mail_ids)}** টি নতুন মেইল পাওয়া গেছে। চেক করা হচ্ছে...")
                
                spam_count = 0
                for mail_id in mail_ids:
                    try:
                        _, msg_data = mail.fetch(mail_id, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                # সাবজেক্ট ডিকোড
                                subject, encoding = decode_header(msg["Subject"])[0]
                                if isinstance(subject, bytes):
                                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                                
                                # বডি বের করা
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if part.get_content_type() == "text/plain":
                                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                                # AI প্রেডিকশন
                                full_text = f"{subject} {body}"
                                vec = cv.transform([full_text])
                                prediction = model.predict(vec)

                                if prediction[0] == 1:
                                    st.error(f"🚨 **SPAM শনাক্ত হয়েছে:** {subject}")
                                    # স্প্যাম ফোল্ডারে মুভ করা
                                    mail.copy(mail_id, "[Gmail]/Spam")
                                    mail.store(mail_id, '+FLAGS', '\\Deleted')
                                    spam_count += 1
                                else:
                                    st.success(f"✅ **নিরাপদ:** {subject}")

                    except Exception as e:
                        st.warning(f"একটি মেইল পড়তে সমস্যা হয়েছে: {e}")

                mail.expunge()
                mail.logout()
                
                if spam_count > 0:
                    st.toast(f"{spam_count} টি স্প্যাম মেইল রিমুভ করা হয়েছে!", icon="🎉")
                else:
                    st.info("কোনো স্প্যাম পাওয়া যায়নি।")

        except Exception as e:
            status_area.error(f"❌ লগইন ব্যর্থ হয়েছে! দয়া করে ইমেইল এবং অ্যাপ পাসওয়ার্ড চেক করুন। ({e})")