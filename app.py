import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from google.genai import types
from io import BytesIO

# ==========================================
# ⚠️ आपकी डिटेल्स (Environment Variables से)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)


# यूज़र की भेजी गई फोटो को थोड़ी देर याद रखने के लिए
user_photos = {}

print("VisionOCR Pro (Direct Gemini) सफलतापूर्वक चालू हो गया है...", flush=True)

# नियमों को rules.txt से पढ़ने के लिए एक फंक्शन
def get_ocr_rules():
    try:
        with open("rules.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "कोई विशेष नियम सेट नहीं किए गए हैं।"

# 1. /start कमांड का स्वागत संदेश
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 नमस्ते! मैं हूँ आपका **VisionOCR Pro** बॉट。\n\n"
        "📸 मुझे कोई भी फोटो भेजें, और मैं उसमें से टेक्स्ट निकाल कर दूँगा!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# 2. जब कोई यूजर फोटो भेजता है
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    # फोटो का ID सेव करें ताकि बटन दबाने पर काम आए
    file_id = message.photo[-1].file_id
    user_photos[message.chat.id] = file_id
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 AI से स्कैन करें (Scan Now)", callback_data="scan_photo"))
    
    bot.reply_to(
        message, 
        "📸 मुझे आपकी फोटो मिल गई है!\n\nटेक्स्ट निकालने के लिए नीचे दिए गए बटन पर क्लिक करें👇", 
        reply_markup=markup
    )

# 3. जब यूज़र 'Scan Now' बटन दबाता है
@bot.callback_query_handler(func=lambda call: call.data == "scan_photo")
def process_photo(call):
    chat_id = call.message.chat.id
    
    if chat_id not in user_photos:
        bot.answer_callback_query(call.id, "⚠️ फोटो पुरानी हो गई है, कृपया दोबारा भेजें।", show_alert=True)
        return
        
    bot.edit_message_text("⏳ AI शक्तिशाली स्कैनिंग कर रहा है, कृपया थोड़ा इंतज़ार करें...", chat_id=chat_id, message_id=call.message.message_id)
    
    try:
        # सेव की गई फोटो डाउनलोड करना
        file_id = user_photos[chat_id]
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_bytes = BytesIO(downloaded_file).getvalue()
        
        # rules.txt से नियम मंगाना
        rules = get_ocr_rules()
        
        # जैमिनी को दी जाने वाली प्रॉम्ट
        prompt = (
            "इस इमेज में जो भी टेक्स्ट लिखा है, उसे पूरी शुद्धता के साथ निकालें।\n\n"
            "⚠️ **OCR के लिए आपको हमेशा इन कड़े नियमों का पालन करना है:**\n"
            f"{rules}\n\n"
            "अब इन नियमों को ध्यान में रखते हुए सही टेक्स्ट आउटपुट दें।"
        )
        
        # जैमिनी को इमेज भेजना
                # जैमिनी को इमेज भेजना
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ]
        )

        
        extracted_text = response.text
        
        if extracted_text and extracted_text.strip():
            bot.edit_message_text(extracted_text, chat_id=chat_id, message_id=call.message.message_id)
        else:
            bot.edit_message_text("❌ माफ़ कीजिएगा, मैं इस इमेज से कोई टेक्स्ट नहीं निकाल पाया।", chat_id=chat_id, message_id=call.message.message_id)
            
        del user_photos[chat_id]
        
    except Exception as e:
        print(f"Error: {e}", flush=True)
        bot.edit_message_text("⚠️ कुछ तकनीकी खराबी आ गई है। कृपया थोड़ी देर बाद दोबारा प्रयास करें।", chat_id=chat_id, message_id=call.message.message_id)

# ==========================================
# रेंडर (Render) के लिए डमी सर्वर
# ==========================================
def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

if __name__ == '__main__':
    # डमी सर्वर को बैकग्राउंड में चालू करना ताकि रेंडर इसे बंद न करे
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # टेलीग्राम बॉट को चालू करना
    bot.infinity_polling()
        
