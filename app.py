import streamlit as st
import imaplib
import email
from email.header import decode_header
import pickle

# পেজ সেটআপ
st.set_page_config(page_title="Force Spam Cleaner", page_icon="💥", layout="centered")

st.title("💥 Force Spam Cleaner")
st.markdown("কোনো ঝামেলা ছাড়া স্প্যাম ফোল্ডার খালি করার টুল।")

# --- সাইডবার ---
with st.sidebar:
    st.header("🔐 Login")
    user_email = st.text_input("Gmail Address")
    user_password = st.text_input("App Password", type="password")
    st.divider()
    st.info("এই টুলটি সরাসরি [Gmail]/Spam ফোল্ডারে কাজ করবে।")

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

# --- ফাংশন: হোয়াইটলিস্ট চেক ---
def is_safe_email(subject, sender):
    # আপনার সেফ লিস্ট
    safe_senders = ["google.com", "linkedin.com", "facebook.com", "streamlit.io", ".edu", ".gov", "upwork.com", "fiverr.com", "binance.com"]
    safe_keywords = ["verification", "code", "otp", "interview", "job", "offer", "class", "exam", "grade", "bkash", "nagad"]
    
    sender = sender.lower()
    subject = subject.lower()

    for s in safe_senders:
        if s in sender: return True
    for w in safe_keywords:
        if w in subject: return True
    return False

# --- মেইন অ্যাকশন ফাংশন ---
def clean_spam_folder(mode):
    if not user_email or not user_password:
        st.warning("আগে বাম পাশে লগইন করুন!")
        return

    status_box = st.status("Connecting to Gmail...", expanded=True)
    
    try:
        # ১. কানেকশন
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, user_password)
        status_box.write("✅ Connected!")
        
        # ২. স্প্যাম ফোল্ডার ওপেন
        mail.select("[Gmail]/Spam")
        
        # ৩. সব মেইল খোঁজা
        typ, data = mail.uid('search', None, "ALL")
        if not data[0]:
            status_box.update(label="Spam folder is already empty! 🎉", state="complete")
            return

        uids = data[0].split()
        total_emails = len(uids)
        status_box.write(f"🔍 Found {total_emails} emails in Spam.")

        uids_to_delete = []

        # ৪. বাছাই করা (যদি Safe Mode হয়)
        if mode == "SAFE":
            progress_bar = status_box.progress(0)
            status_box.write("🤖 analyzing emails...")
            
            for i, uid in enumerate(uids):
                try:
                    res, msg_data = mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    # সাবজেক্ট ডিকোড
                    subject = "No Subject"
                    if msg["Subject"]:
                        decoded_list = decode_header(msg["Subject"])
                        subject_fragment, encoding = decoded_list[0]
                        if isinstance(subject_fragment, bytes):
                            subject = subject_fragment.decode(encoding if encoding else "utf-8")
                        else:
                            subject = str(subject_fragment)
                    
                    sender = msg.get("From", "")

                    # সেফটি চেক
                    if is_safe_email(subject, sender):
                        # এটা সেফ, ডিলিট করব না
                        pass
                    else:
                        # এটা স্প্যাম, ডিলিট লিস্টে যোগ করো
                        uids_to_delete.append(uid)
                        
                except:
                    # পড়তে না পারলে ডিলিট লিস্টে দিয়ে দেব
                    uids_to_delete.append(uid)
                
                progress_bar.progress((i + 1) / total_emails)
        
        else:
            # "ALL" Mode - সব ডিলিট
            uids_to_delete = uids

        # ৫. ডিলিট করা (Batch Delete)
        if uids_to_delete:
            count = len(uids_to_delete)
            status_box.write(f"🗑️ Deleting {count} emails...")
            
            # একসাথে সব ডিলিট (ফাস্ট প্রসেস)
            # IMAP-এ কমা দিয়ে আলাদা করে একসাথে পাঠানো যায়
            batch_ids = b','.join(uids_to_delete)
            
            # ১. সরাসরি ডিলিট ফ্ল্যাগ
            mail.uid('STORE', batch_ids, '+FLAGS', '\\Deleted')
            
            # ২. ধাক্কা দিয়ে বের করা
            mail.expunge()
            
            status_box.update(label=f"✅ Successfully Deleted {count} Emails!", state="complete")
            st.balloons()
            
            # পেজ রিফ্রেশ বাটন
            if st.button("Refresh Page"):
                st.rerun()
        else:
            status_box.update(label="No junk emails found to delete!", state="complete")

        mail.logout()

    except Exception as e:
        status_box.update(label="❌ Failed!", state="error")
        st.error(f"Error: {e}")

# --- বাটন ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🟢 Safe Clean (Recommended)", type="primary"):
        clean_spam_folder(mode="SAFE")

with col2:
    if st.button("🔴 Delete EVERYTHING in Spam"):
        clean_spam_folder(mode="ALL")

st.info("টিপস: 'Safe Clean' আপনার দরকারি মেইল রেখে দেবে। 'Delete EVERYTHING' সব মুছে ফেলবে।")
