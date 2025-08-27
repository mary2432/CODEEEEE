import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from collections import deque

# تنظیمات لاگ‌گیری برای دیباگ بهتر
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- تعریف متغیرهای سراسری ---
# حالا صف انتظار یک دیکشنری است تا اطلاعات کامل کاربران را ذخیره کند
# {user_id: {gender: 'male', partner_gender: 'female', age: '18_25', partner_age: '18_25'}}
waiting_queue = {}
connected_pairs = {}

# --- تعریف کیبوردهای شیشه‌ای (Inline) ---

def get_main_menu():
    keyboard = [[InlineKeyboardButton("🤝 جستجوی پارتنر", callback_data="find_partner")], [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]]
    return InlineKeyboardMarkup(keyboard)

def get_gender_menu():
    keyboard = [[InlineKeyboardButton("آقا 👨", callback_data="set_gender_male"), InlineKeyboardButton("خانم 👩", callback_data="set_gender_female")]]
    return InlineKeyboardMarkup(keyboard)

def get_partner_gender_menu():
    keyboard = [[InlineKeyboardButton("آقا 👨", callback_data="set_partner_gender_male"), InlineKeyboardButton("خانم 👩", callback_data="set_partner_gender_female")], [InlineKeyboardButton("فرقی نمی‌کند 🤷", callback_data="set_partner_gender_any")]]
    return InlineKeyboardMarkup(keyboard)

def get_age_menu():
    keyboard = [
        [InlineKeyboardButton("۱۸ تا ۲۵", callback_data="set_age_18_25"), InlineKeyboardButton("۲۶ تا ۳۵", callback_data="set_age_26_35")],
        [InlineKeyboardButton("۳۶ تا ۴۵", callback_data="set_age_36_45"), InlineKeyboardButton("۴۵ به بالا", callback_data="set_age_45_plus")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_partner_age_menu():
    keyboard = [
        [InlineKeyboardButton("۱۸ تا ۲۵", callback_data="set_partner_age_18_25"), InlineKeyboardButton("۲۶ تا ۳۵", callback_data="set_partner_age_26_35")],
        [InlineKeyboardButton("۳۶ تا ۴۵", callback_data="set_partner_age_36_45"), InlineKeyboardButton("۴۵ به بالا", callback_data="set_partner_age_45_plus")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_menu():
    keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="cancel_search")]]
    return InlineKeyboardMarkup(keyboard)

def get_in_chat_menu():
    keyboard = [[InlineKeyboardButton("❌ پایان چت", callback_data="end_chat")]]
    return InlineKeyboardMarkup(keyboard)

# --- توابع اصلی بات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # پاک کردن وضعیت‌های قبلی کاربر
    context.user_data.clear()
    if user_id in connected_pairs:
        await end_chat_logic(user_id, context)
    if user_id in waiting_queue:
        del waiting_queue[user_id]
    await update.message.reply_text("به بات چت ناشناس خوش آمدید! 😊\nبرای شروع، دکمه زیر را بزنید.", reply_markup=get_main_menu())

async def find_partner_logic(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_prefs = waiting_queue.get(user_id)
    if not user_prefs:
        return

    # جستجو برای یک پارتنر مناسب
    for partner_id, partner_prefs in waiting_queue.items():
        if user_id == partner_id:
            continue

        # چک کردن شرایط دو طرفه
        user_wants_partner = (user_prefs['partner_gender'] == partner_prefs['gender'] or user_prefs['partner_gender'] == 'any')
        partner_wants_user = (partner_prefs['partner_gender'] == user_prefs['gender'] or partner_prefs['partner_gender'] == 'any')
        user_age_match = (user_prefs['partner_age'] == partner_prefs['age'])
        partner_age_match = (partner_prefs['partner_age'] == user_prefs['age'])

        if user_wants_partner and partner_wants_user and user_age_match and partner_age_match:
            # پارتنر پیدا شد!
            del waiting_queue[user_id]
            del waiting_queue[partner_id]
            connected_pairs[user_id] = partner_id
            connected_pairs[partner_id] = user_id
            logger.info(f"Pair found: {user_id} and {partner_id}")

            await context.bot.edit_message_text(chat_id=user_id, message_id=user_prefs['message_id'], text="یک پارتنر پیدا شد! 🎉")
            await context.bot.edit_message_text(chat_id=partner_id, message_id=partner_prefs['message_id'], text="یک پارتنر پیدا شد! 🎉")
            
            await context.bot.send_message(chat_id=user_id, text="حالا می‌توانید هر نوع پیامی ارسال کنید.", reply_markup=get_in_chat_menu())
            await context.bot.send_message(chat_id=partner_id, text="حالا می‌توانید هر نوع پیامی ارسال کنید.", reply_markup=get_in_chat_menu())
            return

async def end_chat_logic(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    if user_id in connected_pairs:
        partner_id = connected_pairs.pop(user_id, None)
        if partner_id:
            connected_pairs.pop(partner_id, None)
        logger.info(f"Chat ended for user {user_id}")
        await context.bot.send_message(chat_id=user_id, text="چت شما پایان یافت.", reply_markup=get_main_menu())
        if partner_id:
            await context.bot.send_message(chat_id=partner_id, text="پارتنر شما چت را ترک کرد.", reply_markup=get_main_menu())
        return True
    return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    command = query.data

    # شروع فرآیند جستجو
    if command == "find_partner":
        context.user_data['prefs'] = {}
        await query.edit_message_text(text="جنسیت شما چیست؟", reply_markup=get_gender_menu())
    
    # انتخاب جنسیت کاربر
    elif command.startswith("set_gender_"):
        context.user_data['prefs']['gender'] = command.split('_')[-1]
        await query.edit_message_text(text="به دنبال چه جنسیتی هستید؟", reply_markup=get_partner_gender_menu())

    # انتخاب جنسیت پارتنر
    elif command.startswith("set_partner_gender_"):
        context.user_data['prefs']['partner_gender'] = command.split('_')[-1]
        await query.edit_message_text(text="محدوده سنی شما چیست؟", reply_markup=get_age_menu())

    # انتخاب سن کاربر
    elif command.startswith("set_age_"):
        context.user_data['prefs']['age'] = "_".join(command.split('_')[2:])
        await query.edit_message_text(text="محدوده سنی پارتنر مورد نظر شما چیست؟", reply_markup=get_partner_age_menu())
    
    # انتخاب سن پارتنر و شروع جستجو
    elif command.startswith("set_partner_age_"):
        context.user_data['prefs']['partner_age'] = "_".join(command.split('_')[3:])
        msg = await query.edit_message_text(text="عالی! در حال جستجو بر اساس معیارهای شما...", reply_markup=get_cancel_menu())
        
        # اضافه کردن کاربر به صف انتظار هوشمند
        waiting_queue[user_id] = context.user_data['prefs']
        waiting_queue[user_id]['message_id'] = msg.message_id
        await find_partner_logic(user_id, context)

    # لغو جستجو
    elif command == "cancel_search":
        if user_id in waiting_queue:
            del waiting_queue[user_id]
        context.user_data.clear()
        await query.edit_message_text(text="جستجو لغو شد.", reply_markup=get_main_menu())
    
    # پایان چت
    elif command == "end_chat":
        await query.edit_message_text(text="چت پایان یافت.")
        await end_chat_logic(user_id, context)
    
    # نمایش راهنما
    elif command == "help":
        help_text = "راهنمای بات چت ناشناس:\n\nبا انتخاب گزینه‌ها، به ربات کمک می‌کنید تا بهترین پارتنر را برای شما پیدا کند."
        await query.edit_message_text(text=help_text, reply_markup=get_main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in connected_pairs:
        partner_id = connected_pairs[user_id]
        await context.bot.copy_message(chat_id=partner_id, from_chat_id=user_id, message_id=update.message.message_id)
    else:
        await update.message.reply_text("شما به کسی متصل نیستید.", reply_markup=get_main_menu())

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

def main():
    TOKEN = "7721393045:AAEUli81XIrHQLoBZrj15oyVWH0aj0qr4kQ"
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
