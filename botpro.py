import logging
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- تنظیمات دیتابیس ---
def init_db():
    """یک دیتابیس SQLite و جدول کاربران را می‌سازد."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT
    )
    """)
    conn.commit()
    conn.close()

def get_user_profile(user_id):
    """پروفایل کاربر را از دیتابیس می‌خواند."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, age, gender FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {"name": user[0], "age": user[1], "gender": user[2]}
    return None

def update_user_profile(user_id, name, age, gender):
    """پروفایل کاربر را در دیتابیس ذخیره یا به‌روزرسانی می‌کند."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (user_id, name, age, gender) VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, age=excluded.age, gender=excluded.gender
    """, (user_id, name, age, gender))
    conn.commit()
    conn.close()

# --- تعریف متغیرهای سراسری ---
waiting_queue = {}
connected_pairs = {}
# --- مراحل مکالمه برای ساخت پروفایل ---
GET_NAME, GET_AGE, GET_GENDER = range(3)

# --- تعریف کیبوردها ---
def get_reply_menu():
    """دکمه دائمی منو را برمی‌گرداند."""
    keyboard = [[KeyboardButton("☰ Menu")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- توابع مکالمه ساخت پروفایل ---
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند ساخت پروفایل."""
    await update.message.reply_text("برای ساخت پروفایل، لطفاً نام خود را وارد کنید:", reply_markup=None)
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نام کاربر را دریافت کرده و سوال بعدی را می‌پرسد."""
    context.user_data['profile_name'] = update.message.text
    await update.message.reply_text("عالی! حالا لطفاً سن خود را به عدد وارد کنید:")
    return GET_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سن کاربر را دریافت کرده و سوال بعدی را می‌پرسد."""
    try:
        age = int(update.message.text)
        if not 18 <= age <= 99:
            await update.message.reply_text("لطفاً یک سن معتبر بین ۱۸ تا ۹۹ وارد کنید.")
            return GET_AGE
        context.user_data['profile_age'] = age
        keyboard = [
            [InlineKeyboardButton("آقا 👨", callback_data="profile_gender_male")],
            [InlineKeyboardButton("خانم 👩", callback_data="profile_gender_female")]
        ]
        await update.message.reply_text("بسیار خب. در نهایت، جنسیت خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_GENDER
    except ValueError:
        await update.message.reply_text("لطفاً سن خود را فقط به صورت عدد وارد کنید.")
        return GET_AGE

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جنسیت کاربر را دریافت و پروفایل را ذخیره می‌کند."""
    query = update.callback_query
    await query.answer()
    gender_map = {"profile_gender_male": "آقا", "profile_gender_female": "خانم"}
    gender = gender_map.get(query.data)
    
    user_id = query.from_user.id
    name = context.user_data['profile_name']
    age = context.user_data['profile_age']
    
    update_user_profile(user_id, name, age, gender)
    
    await query.edit_message_text(f"پروفایل شما با موفقیت تکمیل شد! ✅\n\n"
                                  f"برای دیدن منوی اصلی، دکمه '☰ Menu' را بزنید.")
    return ConversationHandler.END

async def cancel_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرآیند ساخت پروفایل را لغو می‌کند."""
    await update.message.reply_text("ساخت پروفایل لغو شد.", reply_markup=get_reply_menu())
    return ConversationHandler.END


# --- توابع اصلی بات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start را مدیریت می‌کند."""
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if profile:
        await update.message.reply_text("به ربات 'بی نام چت' خوش آمدید!", reply_markup=get_reply_menu())
        await show_main_menu(update, context)
    else:
        keyboard = [[InlineKeyboardButton("✅ تکمیل پروفایل", callback_data="start_profile_setup")]]
        await update.message.reply_text(
            "🔔 فقط چند قدم تا تکمیل پروفایل شما باقی مانده!\n\n"
            "برای شروع گفتگو، ابتدا باید اطلاعات پروفایل خود (نام، سن، جنسیت) را تکمیل کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی را به همراه اطلاعات پروفایل نمایش می‌دهد."""
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        keyboard = [[InlineKeyboardButton("✅ تکمیل پروفایل", callback_data="start_profile_setup")]]
        await update.message.reply_text(
            "شما هنوز پروفایل خود را تکمیل نکرده‌اید!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = (
        f"👤 **پروفایل شما**\n\n"
        f"🔸 **نام:** {profile['name']}\n"
        f"🔸 **سن:** {profile['age']}\n"
        f"🔸 **جنسیت:** {profile['gender']}\n\n"
        "از منوی زیر استفاده کنید:"
    )
    keyboard = [
        [InlineKeyboardButton("🤝 جستجوی پارتنر", callback_data="find_partner")],
        [InlineKeyboardButton("📝 ویرایش پروفایل", callback_data="edit_profile")]
    ]
    
    # اطمینان از ارسال پیام جدید به جای ویرایش
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        await update.callback_query.answer()
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کلیک روی دکمه‌های شیشه‌ای را مدیریت می‌کند."""
    query = update.callback_query
    command = query.data

    if command == "start_profile_setup":
        # این دکمه کاربر را به مکالمه ساخت پروفایل هدایت می‌کند
        # اما خود مکالمه از طریق CommandHandler شروع می‌شود.
        await query.message.reply_text("برای شروع ساخت پروفایل، دستور /profile را ارسال کنید.")
        await query.answer()
    elif command == "edit_profile":
        await query.message.reply_text("برای ویرایش پروفایل، دستور /profile را ارسال کنید.")
        await query.answer()
    # ... سایر دکمه‌های آینده در اینجا مدیریت می‌شوند ...


def main():
    """تابع اصلی برای راه‌اندازی ربات."""
    # ساخت دیتابیس در اولین اجرا
    init_db()

    TOKEN = "7721393045:AAEUli81XIrHQLoBZrj15oyVWH0aj0qr4kQ"
    
    application = Application.builder().token(TOKEN).build()

    # تعریف مکالمه ساخت پروفایل
    profile_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('profile', profile_start),
            CallbackQueryHandler(profile_start, pattern='^start_profile_setup$'),
            CallbackQueryHandler(profile_start, pattern='^edit_profile$')
        ],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GET_GENDER: [CallbackQueryHandler(get_gender, pattern='^profile_gender_')],
        },
        fallbacks=[CommandHandler('cancel', cancel_profile)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(profile_conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    # Handler برای دکمه "Menu"
    application.add_handler(MessageHandler(filters.Regex('^☰ Menu$'), show_main_menu))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()

