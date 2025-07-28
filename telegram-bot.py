import logging
import aiohttp
import os,time

from aiohttp import FormData
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, ContextTypes
)

from dotenv import load_dotenv
load_dotenv(dotenv_path='env.env')


#config
TOKEN = "8320924107:AAH505mhHkOxeY3aLk0GObIpO_KCtY9hhLM"
API_ENDPOINT = os.getenv("API_ENDPOINT")
logging.basicConfig(level=logging.INFO)

#category mappings
VIEW_CATEGORIES = {
    "crl": {
        "Maxilla": "mx",
        "Mandible-MDS": "mds", 
        "Mandible-MLS": "mls",
        "Lateral ventricle": "lv",
        "Head": "head",
        "Gestational sac": "gsac",
        "Thorax": "thorax",
        "Abdomen": "ab",
        "Body(Biparietal diameter)": "bd",
        "Rhombencephalon": "rbp",
        "Diencephalon": "dp",
        "NTAPS": "ntaps",
        "Nasal bone": "nb"
    },
    "nt": {
        "Maxilla": "mx",
        "Mandible-MDS": "mds", 
        "Mandible-MLS": "mls",
        "Lateral ventricle": "lv",
        "Head": "head",
        "Thorax": "thorax",
        "Abdomen": "ab",
        "Rhombencephalon": "rbp",
        "Diencephalon": "dp",
        "Nuchal translucency": "nt",
        "NTAPS": "ntaps",
        "Nasal bone": "nb"
    }
}

#start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send an ultrasound image (JPG/png only) to begin. See /instructions first")

async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instruction_message = """
📋 **Instructions**

🔸 **Step 1:** Send a cropped ultrasound image of a structure you want to analyze. See all structures with /list command
🔸 **Step 2:** Select the ultrasound view (CRL or NT)
🔸 **Step 3:** Choose the anatomical category to analyze
🔸 **Step 4:** Wait for the AI analysis results

📌 **Important notes:**
• Only JPG/PNG images are supported
• Ensure the ultrasound image is clear and properly oriented
• Results are for reference only - always consult a medical professional
• Processing may take a few seconds
• Stop bot with /stop

💡 **Tips:**
• Use high-quality, well-lit images for better accuracy
• Make sure the anatomical structure is clearly visible
• Different views (CRL/NT) have different category options

🆘 **Need help?** Contact support if you encounter any issues @d3ikshr.
    """
    
    await update.message.reply_text(instruction_message, parse_mode='Markdown')

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    list_message = """
📋 **Available Categories by View**

🔍 **CRL view categories:**
• Maxilla • Mandible-MDS • Mandible-MLS
• Lateral ventricle • Head • Gestational sac
• Thorax • Abdomen • Body(Biparietal diameter)
• Rhombencephalon • Diencephalon • NTAPS
• Nasal bone

🔍 **NT view categories:**
• Maxilla • Mandible-MDS • Mandible-MLS
• Lateral ventricle • Head • Thorax
• Abdomen • Rhombencephalon • Diencephalon
• Nuchal translucency • NTAPS • Nasal bone

💡 **Note:** Categories will be shown automatically based on your selected view during analysis.
    """
    
    await update.message.reply_text(list_message, parse_mode='Markdown')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Bot stopped for this chat. Use /start to begin again.")
    # Clear user data
    context.user_data.clear()

# Receive image
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = f"{update.message.from_user.id}_ultrasound.jpg"
    await file.download_to_drive(file_path)
    context.user_data["image_path"] = file_path
    
    # get view
    buttons = [
        [InlineKeyboardButton("CRL", callback_data="view:crl"),
         InlineKeyboardButton("NT", callback_data="view:nt")]
    ]
    await update.message.reply_text(
        "Select the ultrasound view:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

#selcet view
async def handle_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    view = query.data.split(":")[1]
    context.user_data["selected_view"] = view
    
    #get categories for the selected view
    categories = list(VIEW_CATEGORIES[view].keys())
    buttons = [[InlineKeyboardButton(cat, callback_data=f"category:{cat}")]
               for cat in categories]
    await query.edit_message_text(
        "Select anatomical category:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

#get category then upload
async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_display = query.data.split(":")[1]
    context.user_data["selected_category"] = category_display
    
    image_path = context.user_data.get("image_path")
    view = context.user_data.get("selected_view")
    
    if not image_path or not view:
        await query.edit_message_text("Missing image or view.")
        return

    await query.edit_message_text("🔄 Processing image...")
    time.sleep(3)
    await query.edit_message_text("🏥 Building diagnosis, please wait...")

    try:
        #read the image file into memory first
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        #mapping
        category_value = VIEW_CATEGORIES[view][category_display]
        
        #create form data
        form = FormData()
        form.add_field("view", view)
        form.add_field("category", category_value)
        form.add_field("source", "telegram")
        form.add_field("image", image_data, filename="image.jpg", content_type="image/jpeg")
        
        #send request 
        async with aiohttp.ClientSession() as session:
            async with session.post(API_ENDPOINT, data=form) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    message = f"""
📊 **Analysis Results**

🔍 **View:** {result.get('view', view).upper()}
🏥 **Category:** {category_display}

📈 **Confidence:** {result.get('confidence', 0):.2f}%
⚠️ **Reconstruction error:** {result.get('error', 0):.5f}

📋 **Status:** {result.get('comment', 'No comment')}

🩺 **Diagnosis:** {result.get('diagnosis', 'No diagnosis')}

*NOTE: THIS IS NOT PROFESSIONAL MEDICAL ADVICE. LIAS WITH AN EXPERT.*
                    """
                    
                    await query.edit_message_text(message, parse_mode='Markdown')
                     
                else:
                    error_text = await resp.text()
                    await query.edit_message_text(f"❌ Upload failed. Status: {resp.status}\nError: {error_text}")
                    
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
        
    finally:
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                logging.info(f"Cleaned up image file: {image_path}")
        except Exception as e:
            logging.error(f"Error cleaning up file: {e}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("instructions", instructions))
    app.add_handler(CommandHandler("list", list_categories))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_view, pattern="^view:"))
    app.add_handler(CallbackQueryHandler(handle_category, pattern="^category:"))
    app.run_polling()

if __name__ == "__main__":
    main()