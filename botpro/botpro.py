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
waiting_queue = deque()
connected_pairs = {}

# --- تعریف کیبوردهای شیشه‌ای (Inline) ---
def get_main_menu():
    """منوی اصلی برای کاربر آزاد"""
    keyboard = [
        [InlineKeyboardButton("🤝 جستجوی پارتنر", callback_data="find_partner")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_waiting_menu():
    """منوی کاربر در صف انتظار"""
    keyboard = [
        [InlineKeyboardButton("❌ لغو جستجو", callback_data="cancel_search")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_in_chat_menu():
    """منوی کاربر در حال چت"""
    keyboard = [
        [InlineKeyboardButton("❌ پایان چت", callback_data="end_chat")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- توابع اصلی بات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start که پیام خوشامدگویی و منوی اصلی را نمایش می‌دهد."""
    user_id = update.message.from_user.id

    if user_id in connected_pairs:
        await end_chat_logic(user_id, context)
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)

    await update.message.reply_text(
        "به بات چت ناشناس خوش آمدید! 😊\n"
        "برای شروع، دکمه 'جستجوی پارتنر' را بزنید.",
        reply_markup=get_main_menu(),
    )

async def find_partner_logic(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """منطق اصلی پیدا کردن پارتنر چت."""
    if user_id in connected_pairs or user_id in waiting_queue:
        return
    waiting_queue.append(user_id)
    logger.info(f"User {user_id} added to queue. Queue size: {len(waiting_queue)}")

    if len(waiting_queue) >= 2:
        user1_id = waiting_queue.popleft()
        user2_id = waiting_queue.popleft()
        connected_pairs[user1_id] = user2_id
        connected_pairs[user2_id] = user1_id
        logger.info(f"Pair found: {user1_id} and {user2_id}")

        # اطمینان از وجود داده‌های کاربر قبل از دسترسی
        if context.user_data.get(user1_id, {}).get('last_message_id'):
            await context.bot.edit_message_text(chat_id=user1_id, message_id=context.user_data[user1_id]['last_message_id'], text="یک پارتنر پیدا شد! 🎉")
        if context.user_data.get(user2_id, {}).get('last_message_id'):
            await context.bot.edit_message_text(chat_id=user2_id, message_id=context.user_data[user2_id]['last_message_id'], text="یک پارتنر پیدا شد! 🎉")
        
        await context.bot.send_message(chat_id=user1_id, text="حالا می‌توانید چت کنید.", reply_markup=get_in_chat_menu())
        await context.bot.send_message(chat_id=user2_id, text="حالا می‌توانید چت کنید.", reply_markup=get_in_chat_menu())

async def end_chat_logic(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """منطق اصلی برای پایان دادن به چت."""
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
    """مدیریت کلیک روی دکمه‌های شیشه‌ای."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    command = query.data

    if command == "find_partner":
        msg = await query.edit_message_text(text="در حال جستجو برای یک نفر... لطفاً منتظر بمانید.", reply_markup=get_waiting_menu())
        # ذخیره message_id برای ویرایش بعدی
        context.user_data.setdefault(user_id, {})['last_message_id'] = msg.message_id
        await find_partner_logic(user_id, context)
    elif command == "end_chat":
        await query.edit_message_text(text="چت پایان یافت.")
        await end_chat_logic(user_id, context)
    elif command == "cancel_search":
        if user_id in waiting_queue:
            waiting_queue.remove(user_id)
            logger.info(f"User {user_id} cancelled search.")
            await query.edit_message_text(text="جستجو لغو شد.", reply_markup=get_main_menu())
        else:
            await query.edit_message_text(text="شما در صف جستجو نبودید.", reply_markup=get_main_menu())
    elif command == "help":
        help_text = "راهنمای بات چت ناشناس:\n\n🤝 *جستجوی پارتنر*: شما را در صف انتظار قرار می‌دهد.\n\n❌ *لغو جستجو*: شما را از صف خارج می‌کند.\n\n❌ *پایان چت*: به چت فعلی شما خاتمه می‌دهد.\n\nبرای بازگشت به منوی اصلی از دستور /start استفاده کنید."
        await query.edit_message_text(text=help_text, reply_markup=get_main_menu(), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی ارسالی توسط کاربران."""
    user_id = update.message.from_user.id
    if user_id in connected_pairs:
        partner_id = connected_pairs[user_id]
        await context.bot.copy_message(chat_id=partner_id, from_chat_id=user_id, message_id=update.message.message_id)
    else:
        await update.message.reply_text("شما به کسی متصل نیستید.", reply_markup=get_main_menu())

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """لاگ کردن خطاها."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

def main():
    """شروع و اجرای بات."""
    TOKEN = "7721393045:AAEUli81XIrHQLoBZrj15oyVWH0aj0qr4kQ"
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
