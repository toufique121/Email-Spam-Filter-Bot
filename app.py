import streamlit as st
import imaplib
import email
from email.header import decode_header
import joblib

# ==========================================
# ১. পেজ কনফিগারেশন
# ==========================================
st.set_page_config(page_title="AI Spam Cleaner", page_icon="📧")
st.title("📧 AI Email Spam Cleaner (Safe Mode)")
st.write("এই টুলটি আপনার ইনবক্স চেক করবে। **নিরাপদ মেইলগুলো (Whitelist)** অটোমেটিক স্কিপ করা হবে।")

# ==========================================
# ২. নিরাপদ তালিকা (UPDATED WHITELIST) 🛡️
# ==========================================
# এই ডোমেইন বা শব্দগুলো থাকলে বট সেগুলোকে ডিলিট করবে না
WHITELIST_DOMAINS = [
    "duet.ac.bd",          # আপনার ভার্সিটি
    "github.com",          # গিটহাব
    "google.com",          # গুগল
    "accounts.google.com", # গুগল সিকিউরিটি
    "microsoft.com",       # মাইক্রোসফট
    "linkedin.com",        # লিংকডইন
    "kaggle.com",          # ক্যাগল
    "hackerrank.com",      # হ্যাকার‍র‍্যাংক
    "deeplearning.ai",     # পড়াশোনা
    "researchgate.net",    # রিসার্চ
    "bkash.com",           # বিকাশ
    "facebookmail.com",     # ফেসবুক  
    "codeforces.com",  # <--- এটা যোগ করুন
    "medium.com"       # <--- এটা যোগ করুন
]
    
]

# সাবজেক্টে এই শব্দগুলো থাকলেও সেভ করা হবে (যেমন: Submission, Code, Alert)
SAFE_KEYWORDS = ["submission", "verification code", "security alert", "single-use code", "deadline"]

# ==========================================
# ৩. ইউজার ইনপুট
# ==========================================
email_user = st.text_input("আপনার জিমেইল (Gmail):", placeholder="example@gmail.com")
email_pass = st.text_input("আপনার অ্যাপ পাসওয়ার্ড:", type="password")

# ==========================================
# ৪. মডেল লোড
# ==========================================
try:
    model = joblib.load('spam_model.pkl')
    cv = joblib.load('vectorizer.pkl')
except:
    st.error("মডেল ফাইল পাওয়া যায়নি!")

# ==========================================
# ৫. মেইন ফাংশন
# ==========================================
if st.button("🚀 মেইল চেক করুন"):
    if not email_user or not email_pass:
        st.warning("ইমেইল এবং পাসওয়ার্ড দিন।")
    else:
        status_area = st.empty()
        status_area.info("🔗 কানেক্ট হচ্ছে...")
        
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_user, email_pass)
            mail.select("inbox")

            status, messages = mail.search(None, 'UNSEEN')
            mail_ids = messages[0].split()

            if not mail_ids:
                status_area.success("📭 কোনো নতুন মেইল নেই।")
            else:
                spam_count = 0
                for mail_id in mail_ids:
                    try:
                        _, msg_data = mail.fetch(mail_id, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                subject, encoding = decode_header(msg["Subject"])[0]
                                if isinstance(subject, bytes):
                                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                                
                                from_ = str(msg.get("From")).lower()
                                subject_lower = subject.lower()

                                # --- ১. সেফটি চেক (Safety Check) ---
                                is_safe = False
                                
                                # ডোমেইন চেক
                                for domain in WHITELIST_DOMAINS:
                                    if domain in from_:
                                        st.success(f"🛡️ **নিরাপদ (Domain):** {subject}")
                                        is_safe = True
                                        break
                                
                                # কি-ওয়ার্ড চেক (Keywords)
                                if not is_safe:
                                    for keyword in SAFE_KEYWORDS:
                                        if keyword in subject_lower:
                                            st.success(f"🛡️ **নিরাপদ (Keyword):** {subject}")
                                            is_safe = True
                                            break

                                if is_safe:
                                    continue # লুপ স্কিপ করবে

                                # --- ২. স্প্যাম ডিটেকশন ---
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if part.get_content_type() == "text/plain":
                                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                                vec = cv.transform([f"{subject} {body}"])
                                if model.predict(vec)[0] == 1:
                                    st.error(f"🚨 **SPAM শনাক্ত হয়েছে:** {subject}")
                                    mail.copy(mail_id, "[Gmail]/Spam")
                                    mail.store(mail_id, '+FLAGS', '\\Deleted')
                                    spam_count += 1
                                else:
                                    st.success(f"✅ **নিরাপদ:** {subject}")

                    except Exception as e:
                        pass

                mail.expunge()
                mail.logout()
                if spam_count > 0:
                    st.toast(f"{spam_count} টি স্প্যাম ক্লিন করা হয়েছে!")
                else:
                    st.info("কোনো স্প্যাম পাওয়া যায়নি।")

        except Exception as e:
            status_area.error(f"লগইন সমস্যা: {e}")

