import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Google Sheets ချိတ်ဆက်မှု အချက်အလက်များ (အမှန်ပြင်ဆင်ထားပါသည်) ---
CREDENTIALS_DICT = {
    "type": "service_account",
    "project_id": "onion-sheets-manager",
    "private_key_id": "9f50b516cfb0b0a88090757a3e20e8b28ae5db3e",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCpUNbZcMXLOTYD\nvMLQ+ReVSvSYYgc2exYVP50TYrNdmZ1qoUTgUW+egwKBgA/s\nNWP6s2Ip7hWv\nTpLzNqdVGSatxdDOtgW7MCUJvxipbCwBpx3Tn8wI/JCV+K7qLo5k\nnFTZ9R9S+1SN\nJKZHF/siHST1OmBKPD0QSoHShQYZIN81wOjLwB2dwoUBkg48S/ZL\nnX27F4NoTTeb\nS2nQSxra+boKJnVmyCPk0pLxDLYNAOGANKgKzLfJd76c9Ra6RCAY\n\nbXtFSH3TYQG1\nAGZz+PF9xna7hj76BE3C9TB5YRhUkqBfvsS40Z7sEqbXc7r+zg7E\n\nn0rVa09a8lta\nTtljuSYxItiJomVmwVQdx7OPq3Bfm7Cm4MI2MgJY5JNHkmfIPLJy\no\nnha6okv9WDtV\nBhchA9DYbPps=\n-----END PRIVATE KEY-----\n",
    "client_email": "onion-sheets-manager@onion-sheets-manager.iam.gserviceaccount.com",
    "client_id": "103678296831222783303",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.google.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/onion-sheets-manager%40onion-sheets-manager.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

def get_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(CREDENTIALS_DICT, scopes=scope)
        client = gspread.authorize(creds)
        # ⚠️ အစ်ကို့ Google Sheet အမည်မှာ "Onion Data" ဖြစ်ရပါမည်
        return client.open("Onion Data").sheet1
    except Exception as e:
        logger.error(f"Google Sheet Connector Error: {e}")
        return None

reply_keyboard = [
    ['📅 ယနေ့ချုပ်', '📆 ပြီးခဲ့သည့်အပတ်ချုပ်'],
    ['📅 လချုပ်', '🗓️ နှစ်ချုပ်']
]
markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🧅 **MTA ကြက်သွန်နီဈေးနှုန်း စာရင်းကိုင် Bot**\n\n"
        "🟢 **Bot အဆင်သင့် ဖြစ်နေပါပြီခင်ဗျာ!**\n\n"
        "**အသုံးပြုပုံ:**\n"
        "၁။ ဈေးကွက်ပုံစံကို Copy ကူးပြီး တိုက်ရိုက် ပို့ပေးနိုင်ပါသည်။\n"
        "*(ဥပမာ- 2026-05-27, ပင်လယ်, 3500)*\n"
        "၂။ စာရင်းချုပ်များ ကြည့်ချင်ပါက အောက်က ခလုတ်များကို နှိပ်ပါဗျာ။",
        reply_markup=markup,
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    sheet = get_sheet()
    
    if not sheet:
        await update.message.reply_text(
            "❌ **Google Sheet ချိတ်ဆက်မှု အခက်အခဲရှိနေပါသည်**\n\n"
            "ကျေးဇူးပြု၍ အစ်ကို့ Google Drive ထဲက Sheet အမည်ဟာ **`Onion Data`** အတိအကျ ဖြစ်နေရဲ့လား ပြန်စစ်ပေးပါဦးဗျာ။"
        )
        return

    if text == '📅 ယနေ့ချုပ်':
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            records = sheet.get_all_records()
            today_data = [r for r in records if str(r.get('Date')) == today]
            
            if not today_data:
                await update.message.reply_text(f"📭 ယနေ့ ({today}) အတွက် ဒေတာ မရှိသေးပါဗျာ။")
            else:
                msg = f"📊 **ယနေ့ ({today}) စာရင်းချုပ်**\n\n"
                for r in today_data:
                    msg += f"• {r.get('Type', 'N/A')}: {r.get('Price', 0)} ကျပ်\n"
                await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text("❌ စာရင်းဆွဲထုတ်ရာတွင် အမှားအယွင်းရှိနေပါသည်။")
        return

    # ဒေတာသွင်းခြင်းအပိုင်း
    try:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) == 3:
            date_str, crop_type, price_str = parts
            sheet.append_row([date_str, crop_type, int(price_str)])
            await update.message.reply_text(f"✅ ဒေတာကို Google Sheet ထဲသို့ သိမ်းဆည်းပြီးပါပြီ!\n📅 ရက်စွဲ: {date_str}\n🧅 အမျိုးအစား: {crop_type}\n💰 ဈေးနှုန်း: {price_str} ကျပ်")
        else:
            await update.message.reply_text("💡 ကျေးဇူးပြု၍ ဒေတာသွင်းလျှင် `ရက်စွဲ, အမျိုးအစား, ဈေးနှုန်း` ပုံစံအတိုင်း ပို့ပေးပါဗျာ။\nဥပမာ- `2026-05-27, ပင်လယ်, 3500`")
    except Exception as e:
        await update.message.reply_text("❌ ဒေတာသွင်းယူမှု ပုံစံ မှားယွင်းနေပါသည်။")

def main() -> None:
    # 🌟 အစ်ကို့ရဲ့ Bot Token စစ်စစ်ကြီးကို ဤနေရာတွင် တပ်ဆင်ထားပါသည်
    application = Application.builder().token("8733906002:AAE53OpsG2PbWb7fP1sHPRkI0aI0cI7pzeE").build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
        
