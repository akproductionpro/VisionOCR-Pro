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

# यूज़र स्टेट मैनेजमेंट (डेटाबेस की तरह काम करेगा)
user_photos = {}
user_mode = {}
user_status_message = {}

print("VisionOCR Pro (Direct Gemini) सफलतापूर्वक चालू हो गया है...", flush=True)

# नियमों को rules.txt से पढ़ने के लिए एक फंक्शन
def get_ocr_rules():
    try:
        with open("rules.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "कोई विशेष नियम सेट नहीं किए गए हैं।"

# 1. /start और /help कमांड का स्वागत संदेश
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    
    # यूज़र की पुरानी स्टेट को पूरी तरह रीसेट करें
    user_photos[chat_id] = []
    user_mode[chat_id] = 'single'
    if chat_id in user_status_message:
        try:
            bot.delete_message(chat_id, user_status_message[chat_id])
        except:
            pass
        del user_status_message[chat_id]
        
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🖼️ Single Image", callback_data="mode_single"),
        InlineKeyboardButton("📚 Multi Image", callback_data="mode_multi")
    )
    welcome_text = (
        "👋 **नमस्ते! मैं हूँ आपका VisionOCR Pro बॉट।**\n\n"
        "कृपया कार्य शुरू करने के लिए नीचे से अपना मोड चुनें:\n\n"
        "👉 **Single Image Mode:** एक बार में केवल एक फोटो स्कैन करने के लिए।\n"
        "👉 **Multi Image Mode:** एक साथ कई फोटो (पूरा अध्याय/किताब) भेजकर एक साथ स्ट्रक्चर्ड टेक्स्ट निकालने के लिए।"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=markup)

# मोड सेट करने के लिए कॉलबैक हैंडलर
@bot.callback_query_handler(func=lambda call: call.data in ["mode_single", "mode_multi"])
def set_mode(call):
    chat_id = call.message.chat.id
    user_photos[chat_id] = []
    
    if chat_id in user_status_message:
        try:
            bot.delete_message(chat_id, user_status_message[chat_id])
        except:
            pass
        del user_status_message[chat_id]
        
    if call.data == "mode_single":
        user_mode[chat_id] = 'single'
        bot.edit_message_text("🖼️ **Single Image Mode चालू हो गया है!**\n\nअब मुझे कोई भी एक फोटो भेजें, मैं उसका टेक्स्ट निकाल दूंगा।", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")
    else:
        user_mode[chat_id] = 'multi'
        bot.edit_message_text("📚 **Multi Image Mode चालू हो गया है!**\n\nअब आप अपनी सभी फोटो एक साथ सेलेक्ट करके भेज सकते हैं। जब सारी फोटो भेज दें, तब नीचे आने वाले प्रॉसेस बटन पर क्लिक करें।", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")

# 2. जब कोई यूजर फोटो भेजता है
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_mode.get(chat_id, 'single')
    file_id = message.photo[-1].file_id
    
    if chat_id not in user_photos:
        user_photos[chat_id] = []
        
    user_photos[chat_id].append(file_id)
    photo_count = len(user_photos[chat_id])
    
    if mode == 'single':
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔍 AI से स्कैन करें (Scan Now)", callback_data="scan_photo"))
        bot.reply_to(message, "📸 फोटो सफलतापूर्वक मिल गई है!\nनीचे दिए गए बटन पर क्लिक करके स्कैनिंग शुरू करें👇", reply_markup=markup)
    else:
        # मल्टी-मोड में चैट को साफ-सुथरा रखने के लिए पिछला स्टेटस काउंटर मैसेज डिलीट करें
        if chat_id in user_status_message:
            try:
                bot.delete_message(chat_id, user_status_message[chat_id])
            except:
                pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"🚀 {photo_count} फोटो स्कैन करें", callback_data="scan_photo"))
        
        msg = bot.send_message(
            chat_id, 
            f"📚 **मल्टी-इमेज कलेक्शन चालू है...**\n\n"
            f"📸 अब तक कुल **{photo_count}** फोटो जुड़ चुकी हैं।\n\n"
            f"यदि अभी और फोटो बाकी हैं तो भेजते रहें। जब आप पूरी फोटो भेज चुके हों, तो नीचे दिए गए बटन पर क्लिक करें👇", 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
        user_status_message[chat_id] = msg.message_id

# 3. जब यूजर 'Scan Now' या 'स्कैन करें' बटन दबाता है
@bot.callback_query_handler(func=lambda call: call.data == "scan_photo")
def process_photo(call):
    chat_id = call.message.chat.id
    
    if chat_id not in user_photos or len(user_photos[chat_id]) == 0:
        bot.answer_callback_query(call.id, "⚠️ कोई फोटो नहीं मिली! कृपया पहले फोटो भेजें।", show_alert=True)
        return
        
    bot.edit_message_text("⏳ AI शक्तिशाली स्कैनिंग कर रहा है... सभी इमेजेस को प्रोसेस किया जा रहा है, कृपया थोड़ा इंतजार करें...", chat_id=chat_id, message_id=call.message.message_id)
    
    try:
        contents = []
        # सभी फोटो को एक-एक करके डाउनलोड करके जेमिनी पार्ट्स में बदलना
        for f_id in user_photos[chat_id]:
            file_info = bot.get_file(f_id)
            downloaded_file = bot.download_file(file_info.file_path)
            contents.append(types.Part.from_bytes(data=downloaded_file, mime_type='image/jpeg'))
        
        # rules.txt से नियम लोड करना
        rules = get_ocr_rules()
        prompt = (
            "इन सभी इमेजेस में जो भी टेक्स्ट लिखा है, उसे पूरी शुद्धता और सही क्रम (structure) के साथ निकालें।\n\n"
            "⚠️ **OCR के लिए आपको हमेशा इन कड़े नियमों का पालन करना है:**\n"
            f"{rules}\n\n"
            "अब इन नियमों को ध्यान में रखते हुए एक ही साथ सही और व्यवस्थित टेक्स्ट आउटपुट प्रदान करें।"
        )
        contents.append(prompt)
        
        # जेमिनी API से कंटेंट जनरेट करना (आपका पसंदीदा वर्किंग मॉडल)
        response = ai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents
        )
        
        extracted_text = response.text
        
        # लोडिंग मैसेज को सुरक्षित रूप से हटाना (क्रैश प्रूफ लेयर)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
            
        if chat_id in user_status_message:
            del user_status_message[chat_id]
            
        if extracted_text and extracted_text.strip():
            # यदि टेक्स्ट बहुत बड़ा है (4000 कैरेक्टर से ज्यादा), तो उसे फाइल के रूप में भी भेजेंगे 
            if len(extracted_text) > 4000:
                bot.send_message(chat_id, "📝 **बड़ा अध्याय होने के कारण मैं इसे एक फाइल के रूप में भी प्रदान कर रहा हूँ ताकि इसका स्ट्रक्चर न बिगड़े:**")
                
                # स्ट्रिंग को फाइल ऑब्जेक्ट (BytesIO) में बदलना
                text_file = BytesIO(extracted_text.encode('utf-8'))
                text_file.name = "Scanned_Chapter.txt"
                bot.send_document(chat_id, text_file, caption="📚 आपका पूरा अध्याय एक साथ इस फाइल में सुरक्षित है।")
                
                # बैकअप के तौर पर स्क्रीन पर भी टुकड़े भेज देते हैं
                for i in range(0, len(extracted_text), 4000):
                    bot.send_message(chat_id, extracted_text[i:i+4000])
            else:
                bot.send_message(chat_id, extracted_text)
        else:
            bot.send_message(chat_id, "❌ माफ़ कीजिएगा, मैं इन इमेज से कोई टेक्स्ट नहीं निकाल पाया। कृपया इमेज की क्वालिटी चेक करें।")
            
        # काम सफलतापूर्वक पूरा होने के बाद लिस्ट खाली करें
        user_photos[chat_id] = []
        
    except Exception as e:
        print(f"Error: {e}", flush=True)
        try:
            bot.send_message(chat_id, f"⚠️ कुछ तकनीकी खराबी आ गई है। कृपया थोड़ी देर बाद दोबारा प्रयास करें।\n\n*(विवरण: {str(e)})*")
        except:
            pass
        # एरर आने पर भी लिस्ट रीसेट करें ताकि बॉट स्टक न हो
        user_photos[chat_id] = []

# ==========================================
# 🌐 रेंडर (Render) के लिए डमी सर्वर
# ==========================================
def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

if __name__ == '__main__':
    # डमी सर्वर को बैकग्राउंड थ्रेड में चालू करना ताकि रेंडर इसे एक्टिव रखे
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # टेलीग्राम बॉट को चालू करना (इन्फिनिटी पोलिंग मोड)
    bot.infinity_polling()
    
