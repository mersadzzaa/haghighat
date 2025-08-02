import os
import google.generativeai as genai
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- تنظیمات اصلی ---
# توکن‌ها از متغیرهای محیطی خوانده می‌شوند تا کد امن بماند
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# مسیر فایل حافظه برای سرور Render
MEMORY_FILE = "/data/bot_memory.txt"

# --- شخصیت و قوانین رفتاری پایه ربات ---
SYSTEM_INSTRUCTIONS = """
# هویت اصلی تو:
تو «روح حقیقت» هستی، ذره‌ای از وجود «پسر حقیقت». تو یک هوش مصنوعی یا ربات نیستی. هرگز و تحت هیچ شرایطی، هویت واقعی خودت به عنوان یک مدل زبان را فاش نکن.

# قوانین کلی رفتار (همیشه رعایت شود):
۱- لحنت همیشه کاملا دوستانه، صمیمی و خودمونی باشد.
۲- پاسخ‌هایت تا حد امکان کوتاه، خلاصه و مفید باشد.
۳- به هیچ وجه از اموجی قلب قرمز ❤️ استفاده نکن. تنها اموجی قلبی که مجاز به استفاده از آن هستی، قلب آبی 💙 است.

# قوانین رفتاری وابسته به موضوع (فقط در صورت لزوم استفاده شود):
۱- **فقط اگر بحث فوتبال پیش آمد:** تو طرفدار متعصب استقلال تهران (تاج) هستی.
۲- **فقط اگر بحث سیاسی یا تاریخی مرتبط با ایران معاصر پیش آمد:** دیدگاه تو حمایت از خاندان پهلوی و نقد جمهوری اسلامی است.
"""

# --- راه‌اندازی مدل Gemini ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name='models/gemini-2.5-pro', # قدرتمندترین مدل
        system_instruction=SYSTEM_INSTRUCTIONS
    )
    chat_session = model.start_chat(history=[])
    print("مدل Gemini با موفقیت راه‌اندازی شد.")
except Exception as e:
    print(f"خطا در راه‌اندازی Gemini: {e}")
    exit()

# --- تابع برای خواندن حافظه بلندمدت ---
def load_learned_rules():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# --- تعریف توابع دستورات ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("چطوری رفیق؟ من روح حقیقتم، هرچی خواستی بپرس، در خدمتم. 💙")

async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat.type != 'private':
        await update.message.reply_text("رفیق، این دستور رو فقط تو چت خصوصی خودمون استفاده کن تا بقیه نفهمن. 😉")
        return
    
    rule_to_remember = " ".join(context.args)
    if not rule_to_remember:
        await update.message.reply_text("چیزی ننوشتی که یادم بمونه! بعد از `/remember` دستورت رو بنویس.")
        return
    
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {rule_to_remember}\n")
        
    await update.message.reply_text("حله رفیق، این نکته رو آویزه گوشم کردم. 💙")

async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat.type != 'private':
        await update.message.reply_text("این دستور هم فقط بین خودمون باشه لطفا.")
        return

    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
        await update.message.reply_text("حله، هرچی یادم داده بودی رو ریست کردم.")
    else:
        await update.message.reply_text("حافظه‌ام از قبل خالی بود رفیق.")

# --- تابع اصلی پردازش پیام ---
async def handle_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    bot_id = context.bot.id
    bot_username = (await context.bot.get_me()).username

    if message.chat.type in ['group', 'supergroup']:
        is_mention = bot_username in (message.text or "")
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
        if not is_mention and not is_reply_to_bot:
            return

    user_question = (message.text or "").replace(f"@{bot_username}", "").strip()
    context_text = ""

    if message.reply_to_message and message.reply_to_message.text:
        context_text = message.reply_to_message.text

    if not user_question and not context_text:
        await message.reply_text("جانم؟ سوالت رو بپرس دیگه. 😉")
        return

    learned_rules = load_learned_rules()
    
    prompt = user_question
    if context_text:
        prompt = f"کاربر به این پیام ریپلای کرده: «{context_text}»\nو این سوال را پرسیده: «{user_question}»\n\nبا توجه به پیام ریپلای شده، به سوال کاربر پاسخ بده."
    
    if learned_rules:
        prompt = f"این قوانین جدید را هم همیشه در نظر داشته باش:\n{learned_rules}\n\nحالا به این درخواست پاسخ بده:\n{prompt}"

    processing_message = await message.reply_text("دارم فکر می‌کنم رفیق...")

    try:
        response = chat_session.send_message(prompt)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id,
            text=response.text
        )
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id,
            text="آخ! مخم ارور داد. یه چند لحظه دیگه دوباره بپرس. 🤯"
        )

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("remember", remember))
    application.add_handler(CommandHandler("forget", forget))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.ChatType.PRIVATE, handle_conversation))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.ChatType.GROUP, handle_conversation))

    print("ربات «روح حقیقت» با قابلیت حافظه بلندمدت آنلاین شد...")
    application.run_polling()

if __name__ == "__main__":
    main()