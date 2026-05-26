import json
import os
import re
import logging
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
FILE_NAME = "onion_data.json"
CUSTOM_REPORT_START, CUSTOM_REPORT_END, DELETE_DATE = range(3)

def save_data(data):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def clean_text_and_num(text):
    myanmar_digits = {'၀':'0','၁':'1','၂':'2','၃':'3','၄':'4','၅':'5','၆鍵':'6','၇':'7','၈':'8','၉':'9', '၆':'6'}
    for m, e in myanmar_digits.items():
        text = text.replace(m, e)
    text = text.replace("သန့်", "သန့်").replace("သန်", "သန့်")
    return text

def parse_price(price_str):
    price_str = clean_text_and_num(price_str).strip()
    if re.search(r'[a-zA-Z]', price_str) or "မရှိ" in price_str or "No" in price_str:
        return 0.0
    nums = re.findall(r'\d+', price_str)
    if len(nums) == 2:
        return (float(nums[0]) + float(nums[1])) / 2
    elif len(nums) == 1:
        return float(nums[0])
    return 0.0

def parse_onion_post(post_text):
    cleaned_text = clean_text_and_num(post_text)
    
    date_match = re.search(r'(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})', cleaned_text)
    if date_match:
        d, m, y = date_match.groups()
        date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    car_match = re.search(r'ကားဝင်\s*(\d+)', cleaned_text)
    total_cars = int(car_match.group(1)) if car_match else 0
    total_viss = total_cars * 10000
    
    lines = cleaned_text.split('\n')
    city_chunks = {}
    current_city = None
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        if line_strip.startswith("#") and "စျေးကွက်" not in line_strip:
            if not any(keyword in line_strip for keyword in ["ရှယ်", "လတ်ကြီး", "လတ်သန့်", "လတ်သန်", "လတ်ချော", "ပစ္စည်း", "ဆွေမျိုး"]):
                city_name = re.sub(r'[#။၊❤️💙🖤💜✨🌟\s]', '', line_strip)
                for stop_word in ["ဖွင့်", "ဖွင့်", "ဈေး", "စျေး", "အစုံ"]:
                    if stop_word in city_name:
                        city_name = city_name.split(stop_word)[0]
                
                if city_name:
                    current_city = city_name
                    city_chunks[current_city] = []
                    continue
                    
        if current_city:
            city_chunks[current_city].append(line_strip)
            
    entries = []
    for city_name, chunk_lines in city_chunks.items():
        share_val, latkyi_val, latthan_val, lathaw_val = 0.0, 0.0, 0.0, 0.0
        has_data = False
        for cl in chunk_lines:
            val_match = re.search(r'(?:ရှယ်|လတ်ကြီး|လတ်သန့်|လတ်သန်|လတ်ချော)\s*([^\n]+)', cl)
            if val_match:
                val_str = val_match.group(1)
                if "ရှယ်" in cl:
                    share_val = parse_price(val_str)
                    has_data = True
                elif "လတ်ကြီး" in cl:
                    latkyi_val = parse_price(val_str)
                    has_data = True
                elif "လတ်သန့်" in cl or "လတ်သန်" in cl:
                    latthan_val = parse_price(val_str)
                    has_data = True
                elif "လတ်ချော" in cl:
                    lathaw_val = parse_price(val_str)
                    has_data = True
                    
        if has_data:
            entry = {
                "city": city_name,
                "date": date_str,
                "share": share_val,
                "latkyi": latkyi_val,
                "latthan": latthan_val,
                "lathaw": lathaw_val,
                "viss": float(total_viss) if len(entries) == 0 else 0.0,
                "car": total_cars if len(entries) == 0 else 0
            }
            entries.append(entry)
            
    return entries, date_str, total_cars, total_viss

def generate_summary_text(filtered_records, title):
    if not filtered_records:
        return f"📭 {title} အတွက် ရှာဖွေထားသော ဒေတာမရှိသေးပါဗျာ။"
    total_cars = sum(r.get('car', 0) for r in filtered_records)
    total_viss = sum(r.get('viss', 0) for r in filtered_records)
    
    city_data = {}
    for r in filtered_records:
        c = r['city']
        if c not in city_data:
            city_data[c] = {"share": [], "latkyi": [], "latthan": [], "lathaw": [], "count": 0}
        if r['share'] > 0: city_data[c]['share'].append(r['share'])
        if r['latkyi'] > 0: city_data[c]['latkyi'].append(r['latkyi'])
        if r['latthan'] > 0: city_data[c]['latthan'].append(r['latthan'])
        if r['lathaw'] > 0: city_data[c]['lathaw'].append(r['lathaw'])
        city_data[c]['count'] += 1

    text = f"📊 *{title} စာရင်းချုပ်*\n"
    text += f"🚛 စုစုပေါင်းကားဝင်: {total_cars} စီး\n"
    text += f"⚖️ စုစုပေါင်းကုန်ချိန်: {total_viss:,.0f} ပိသာ\n"
    text += "----------------------------------------\n\n"
    
    for city, d in city_data.items():
        avg_share = sum(d['share'])/len(d['share']) if d['share'] else 0
        avg_latkyi = sum(d['latkyi'])/len(d['latkyi']) if d['latkyi'] else 0
        avg_latthan = sum(d['latthan'])/len(d['latthan']) if d['latthan'] else 0
        avg_lathaw = sum(d['lathaw'])/len(d['lathaw']) if d['lathaw'] else 0
        text += (
            f"🏙️ *{city}* (ပျမ်းမျှဈေးနှုန်းများ)\n"
            f"• ရှယ်: {avg_share:,.0f} | လတ်ကြီး: {avg_latkyi:,.0f}\n"
            f"• လတ်သန့်: {avg_latthan:,.0f} | လတ်ချော: {avg_lathaw:,.0f}\n\n"
        )
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 ယနေ့ချုပ်", callback_data="report_today"), InlineKeyboardButton("📆 ပြီးခဲ့သည့်အပတ်ချုပ်", callback_data="report_week")],
        [InlineKeyboardButton("📅 လချုပ်", callback_data="report_month"), InlineKeyboardButton("🗓️ နှစ်ချုပ်", callback_data="report_year")],
        [InlineKeyboardButton("🔍 စိတ်ကြိုက်ရက်စွဲချုပ်", callback_data="report_custom")],
        [InlineKeyboardButton("❌ ရက်စွဲအလိုက် ဒေတာဖျက်ရန်", callback_data="delete_data_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🧅 *MTA ကြက်သွန်နီဈေးနှုန်း စာရင်းကိုင် Bot*\n\n"
        "🟢 *Bot အဆင်သင့်ဖြစ်နေပါပြီ!*\n\n"
        "**အသုံးပြုပုံ:**\n"
        "၁။ ဈေးကွက်ပို့စ်ကို Copy ကူးပြီး တိုက်ရိုက် ပို့ပေးနိုင်ပါတယ်။\n"
        "၂။ စာရင်းချုပ်များ ကြည့်ချင်ပါက အောက်က ခလုတ်များကို နှိပ်ပါဗျာ။"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_text = update.message.text
    loading_msg = await update.message.reply_text("🔄 စာသားများနှင့် ရက်စွဲများကို စစ်ဆေးနေပါသည်...")
    try:
        entries, date_str, total_cars, total_viss = parse_onion_post(post_text)
        if not entries:
            await loading_msg.edit_text("❌ စာသားထဲကနေ ဒေတာများကို ဖတ်လို့မရပါ။ ပုံစံပြောင်းလဲသွားခြင်းကြောင့် ဖြစ်နိုင်ပါသည်။")
            return
            
        data = load_data()
        is_duplicate = any(r['date'] == date_str for r in data)
        if is_duplicate:
            await loading_msg.edit_text(f"⚠️ *ဒေတာ ထည့်သွင်း၍မရပါ!*\n\nရက်စွဲ ({date_str}) အတွက် ဈေးနှုန်းဒေတာများ စနစ်ထဲမှာ ရှိပြီးသားဖြစ်နေလို့ လက်မခံပါဗျာ။")
            return
            
        data.extend(entries)
        save_data(data)
        
        result_text = f"✅ *ဒေတာ အသစ်သိမ်းဆည်းပြီးပါပြီ။ ({date_str})*\n"
        result_text += f"🚛 *ဘုရင့်နောင် ကားဝင်:* {total_cars} စီး\n"
        result_text += f"⚖️ *စုစုပေါင်း ကုန်ချိန်:* {total_viss:,.0f} ပိသာ\n"
        result_text += "----------------------------------------\n\n"
        for e in entries:
            result_text += f"🏙️ *{e['city']}*\n• ရှယ်: {e['share']:,.0f} | လတ်ကြီး: {e['latkyi']:,.0f}\n• လတ်သန့်: {e['latthan']:,.0f} | လတ်ချော: {e['lathaw']:,.0f}\n\n"
        await loading_msg.edit_text(result_text, parse_mode="Markdown")
    except Exception as e:
        await loading_msg.edit_text("❌ Error: ဒေတာဖတ်ရာတွင် အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါသည်။")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    records = load_data()
    today = datetime.now()
    
    if query.data == "report_today":
        today_str = today.strftime("%Y-%m-%d")
        filtered = [r for r in records if r['date'] == today_str]
        await query.message.reply_text(generate_summary_text(filtered, f"ယနေ့ ({today_str})"), parse_mode="Markdown")
    elif query.data == "report_week":
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        filtered = [r for r in records if start_date <= r['date'] <= end_date]
        await query.message.reply_text(generate_summary_text(filtered, "ပြီးခဲ့သည့်ပတ်ချုပ် (7 ရက်စာ)"), parse_mode="Markdown")
    elif query.data == "report_month":
        month_str = today.strftime("%Y-%m")
        filtered = [r for r in records if r['date'].startswith(month_str)]
        await query.message.reply_text(generate_summary_text(filtered, f"ယခုလချုပ် ({today.strftime('%B %Y')})"), parse_mode="Markdown")
    elif query.data == "report_year":
        year_str = today.strftime("%Y")
        filtered = [r for r in records if r['date'].startswith(year_str)]
        await query.message.reply_text(generate_summary_text(filtered, f"ယခုနှစ်ချုပ် ({year_str})"), parse_mode="Markdown")
    elif query.data == "report_custom":
        await query.message.reply_text("🔍 *စိတ်ကြိုက်ရက်စွဲချုပ်ကြည့်ရန်*\n\nစမည့်ရက်စွဲကို `နေ့.လ.ခုနှစ်` ပုံစံဖြင့် ရိုက်ပေးပါဗျာ။\nဥပမာ - `1.5.2026`")
        return CUSTOM_REPORT_START
    elif query.data == "delete_data_menu":
        await query.message.reply_text("❌ *ဒေတာဖျက်ရန်*\n\nဖျက်လိုသော ရက်စွဲကို `နေ့.လ.ခုနှစ်` ပုံစံဖြင့် တိကျစွာ ရိုက်ပေးပါဗျာ။\nဥပမာ - `23.5.2026`")
        return DELETE_DATE

async def custom_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = clean_text_and_num(update.message.text)
    match = re.search(r'(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})', user_input)
    if not match:
        await update.message.reply_text("❌ ရက်စွဲပုံစံ မမှန်ပါ။ `နေ့.လ.ခုနှစ်` ပြန်ရိုက်ပေးပါဗျာ။")
        return CUSTOM_REPORT_START
    d, m, y = match.groups()
    context.user_data['start_date'] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    await update.message.reply_text("➡️ နောက်ဆုံး ရက်စွဲကို `နေ့.လ.ခုနှစ်` အတိုင်း ထပ်မံရိုက်ပေးပါဗျာ။\nဥပမာ - `26.5.2026`")
    return CUSTOM_REPORT_END

async def custom_report_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = clean_text_and_num(update.message.text)
    match = re.search(r'(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})', user_input)
    if not match:
        await update.message.reply_text("❌ ရက်စွဲပုံစံ မမှန်ပါ။ `နေ့.လ.ခုနှစ်` ပြန်ရိုက်ပေးပါဗျာ။")
        return CUSTOM_REPORT_END
    d, m, y = match.groups()
    end_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    start_date = context.user_data['start_date']
    records = load_data()
    filtered = [r for r in records if start_date <= r['date'] <= end_date]
    await update.message.reply_text(generate_summary_text(filtered, f"📅 ({start_date}) မှ ({end_date}) အထိ"), parse_mode="Markdown")
    return ConversationHandler.END

async def delete_date_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = clean_text_and_num(update.message.text)
    match = re.search(r'(\d{1,2})[\./-](\d{1,2})[\./-](\d{4})', user_input)
    if not match:
        await update.message.reply_text("❌ ရက်စွဲပုံစံ မမှန်ပါ။ `နေ့.လ.ခုနှစ်` ပြန်ရိုက်ပေးပါဗျာ။")
        return DELETE_DATE
    d, m, y = match.groups()
    target_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    records = load_data()
    original_count = len(records)
    updated_records = [r for r in records if r['date'] != target_date]
    if len(updated_records) == original_count:
        await update.message.reply_text(f"📭 စနစ်ထဲမှာ ရက်စွဲ ({target_date}) အတွက် ဒေတာ ရှာမတွေ့ပါ။")
    else:
        save_data(updated_records)
        await update.message.reply_text(f"✅ ရက်စွဲ (*{target_date}*) အတွက် ဒေတာအားလုံး ဖျက်ပြီးပါပြီ။", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။")
    return ConversationHandler.END

def main():
    BOT_TOKEN = "8733906002:AAEWuxo9_sVTbW61udQ1ohBMq9eI5PGoceU"
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(report_custom|delete_data_menu)$")],
        states={
            CUSTOM_REPORT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_report_start)],
            CUSTOM_REPORT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_report_end)],
            DELETE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_date_data)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_post))

    print("🤖 MTA Advanced Bot is running on Termux...")
    application.run_polling()

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"🔄 Bot crash ဖြစ်သွားသဖြင့် ၅ စက္ကန့်အကြာတွင် အလိုအလျောက် ပြန်စပါမည်။ Error: {e}")
            time.sleep(5)

