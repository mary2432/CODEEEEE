import logging
import asyncio
import os # <--- این خط اضافه شده
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

# ... (بقیه کد شما بدون تغییر باقی می‌ماند) ...

# --- توابع اصلی بات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    if user_id in connected_pairs:
        await end_chat_logic(user_id, context)
    if user_id in waiting_queue:
        del waiting_queue[user_id]
    # *** تغییر اصلی اینجاست ***
    await update.message.reply_text("به ربات 'بی نام چت' خوش آمدید! 😊\nبرای شروع، دکمه زیر را بزنید.", reply_markup=get_main_menu())

# ... (تمام توابع دیگر شما بدون تغییر باقی می‌مانند) ...

def main():
    # توکن از متغیرهای مخفی خوانده می‌شود
    TOKEN = os.environ.get('TOKEN') # <--- این خط تغییر کرده
    if not TOKEN:
        print("!!! توکن ربات در بخش Secrets تعریف نشده است !!!")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    # این بخش برای سازگاری با Replit خالی می‌ماند
    # Replit به طور خودکار تابع main را از فایل اصلی اجرا می‌کند
    # اما برای اطمینان، ما آن را اینجا هم فراخوانی می‌کنیم
    main()

# --- این بخش‌ها برای کامل بودن کد در اینجا تکرار شده‌اند ---
# --- شما فقط باید خطوط مشخص شده را در کد خودتان تغییر دهید ---

# ... (تمام کیبوردها و توابع دیگر که در کد اصلی شما وجود دارد) ...
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# {user_id: {gender: 'male', partner_gender: 'female', age: '18_25', partner_age: 'any'}}
waiting_queue = {}
connected_pairs = {}

def get_main_menu():
    keyboard = [[InlineKeyboardButton("🤝 جستجوی پارتنر", callback_data="find_partner")], [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]]
    return InlineKeyboardMarkup(keyboard)

def get_gender_menu():
    keyboard = [[InlineKeyboardButton("آقا 👨", callback_data="set_gender_male"), InlineKeyboardButton("خانم 👩", callback_data="set_gender_female")]]
    return InlineKeyboardMarkup(keyboard)

def get_partner_gender_menu():
    keyboard = [
        [InlineKeyboardButton("آقا 👨", callback_data="set_partner_gender_male"), InlineKeyboardButton("خانم 👩", callback_data="set_partner_gender_female")],
        [InlineKeyboardButton("فرقی نمی‌کند 🤷", callback_data="set_partner_gender_any")],
        [InlineKeyboardButton("بازگشت 🔙", callback_data="back_to_gender")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_age_menu():
    keyboard = [
        [InlineKeyboardButton("۱۸ تا ۲۵", callback_data="set_age_18_25"), InlineKeyboardButton("۲۶ تا ۳۵", callback_data="set_age_26_35")],
        [InlineKeyboardButton("۳۶ تا ۴۵", callback_data="set_age_36_45"), InlineKeyboardButton("۴۵ به بالا", callback_data="set_age_45_plus")],
        [InlineKeyboardButton("بازگشت 🔙", callback_data="back_to_partner_gender")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_partner_age_menu():
    keyboard = [
        [InlineKeyboardButton("۱۸ تا ۲۵", callback_data="set_partner_age_18_25"), InlineKeyboardButton("۲۶ تا ۳۵", callback_data="set_partner_age_26_35")],
        [InlineKeyboardButton("۳۶ تا ۴۵", callback_data="set_partner_age_36_45"), InlineKeyboardButton("۴۵ به بالا", callback_data="set_partner_age_45_plus")],
        [InlineKeyboardButton("فرقی نمی‌کند 🤷", callback_data="set_partner_age_any")],
        [InlineKeyboardButton("بازگشت 🔙", callback_data="back_to_age")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_menu():
    keyboard = [[InlineKeyboardButton("❌ لغو جستجو", callback_data="cancel_search")]]
    return InlineKeyboardMarkup(keyboard)

def get_in_chat_menu():
    keyboard = [[InlineKeyboardButton("❌ پایان چت", callback_data="end_chat")]]
    return InlineKeyboardMarkup(keyboard)

async def find_partner_logic(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_prefs = waiting_queue.get(user_id)
    if not user_prefs: return

    for partner_id, partner_prefs in list(waiting_queue.items()):
        if user_id == partner_id: continue

        user_wants_partner_gender = (user_prefs['partner_gender'] == partner_prefs['gender'] or user_prefs['partner_gender'] == 'any')
        partner_wants_user_gender = (partner_prefs['partner_gender'] == user_prefs['gender'] or partner_prefs['partner_gender'] == 'any')
        
        user_wants_partner_age = (user_prefs['partner_age'] == partner_prefs['age'] or user_prefs['partner_age'] == 'any')
        partner_wants_user_age = (partner_prefs['partner_age'] == user_prefs['age'] or partner_prefs['partner_age'] == 'any')

        if user_wants_partner_gender and partner_wants_user_gender and user_wants_partner_age and partner_wants_user_age:
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
        if partner_id: connected_pairs.pop(partner_id, None)
        logger.info(f"Chat ended for user {user_id}")
        await context.bot.send_message(chat_id=user_id, text="چت شما پایان یافت.", reply_markup=get_main_menu())
        if partner_id: await context.bot.send_message(chat_id=partner_id, text="پارتنر شما چت را ترک کرد.", reply_markup=get_main_menu())
        return True
    return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    command = query.data

    # --- مدیریت دکمه‌های بازگشت ---
    if command == "back_to_gender":
        await query.edit_message_text(text="جنسیت شما چیست؟", reply_markup=get_gender_menu())
        return
    if command == "back_to_partner_gender":
        await query.edit_message_text(text="تمایل به گفتگو با چه کسی دارید؟", reply_markup=get_partner_gender_menu())
        return
    if command == "back_to_age":
        await query.edit_message_text(text="محدوده سنی شما چیست؟", reply_markup=get_age_menu())
        return

    # --- فرآیند اصلی انتخاب ---
    if command == "find_partner":
        context.user_data['prefs'] = {}
        await query.edit_message_text(text="جنسیت شما چیست؟", reply_markup=get_gender_menu())
    
    elif command.startswith("set_gender_"):
        context.user_data['prefs']['gender'] = command.split('_')[-1]
        await query.edit_message_text(text="تمایل به گفتگو با چه کسی دارید؟", reply_markup=get_partner_gender_menu())

    elif command.startswith("set_partner_gender_"):
        context.user_data['prefs']['partner_gender'] = command.split('_')[-1]
        await query.edit_message_text(text="محدوده سنی شما چیست؟", reply_markup=get_age_menu())

    elif command.startswith("set_age_"):
        context.user_data['prefs']['age'] = "_".join(command.split('_')[2:])
        await query.edit_message_text(text="محدوده سنی پارتنر مورد نظر شما چیست؟", reply_markup=get_partner_age_menu())
    
    elif command.startswith("set_partner_age_"):
        context.user_data['prefs']['partner_age'] = "_".join(command.split('_')[3:])
        msg = await query.edit_message_text(text="عالی! در حال جستجو بر اساس معیارهای شما...", reply_markup=get_cancel_menu())
        
        waiting_queue[user_id] = context.user_data['prefs']
        waiting_queue[user_id]['message_id'] = msg.message_id
        await find_partner_logic(user_id, context)

    elif command == "cancel_search":
        if user_id in waiting_queue: del waiting_queue[user_id]
        context.user_data.clear()
        await query.edit_message_text(text="جستجو لغو شد.", reply_markup=get_main_menu())
    
    elif command == "end_chat":
        await query.edit_message_text(text="چت پایان یافت.")
        await end_chat_logic(user_id, context)
    
    elif command == "help":
        help_text = "راهنمای بات چت ناشناس:\n\nبا انتخاب گزینه‌ها، به ربات کمک می‌کنید تا بهترین پارتنر را برای شما پیدا کند."
        await query.edit_message_text(text=help_text, reply_markup=get_main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in connected_pairs:
        partner_id = connected_pairs[user_id]
        await context.bot.copy_message(chat_id=partner_id, from_chat_id=user_id, message_id=update.message.message_id)
    else:
        await update.message.reply_text("شما به کسی متصل نیستید.", reply_markup=get_main_menu())

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

