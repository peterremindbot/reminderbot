import smtplib
import schedule
import time
import threading
import base64
import os
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import anthropic
from PIL import Image
import io

load_dotenv()

# ── CONFIG ──────────────────────────────────────────────
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
VERIZON_SMS_GATEWAY = os.getenv("VERIZON_SMS_GATEWAY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# ────────────────────────────────────────────────────────

app = Flask(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

completed_meals = set()
snoozed_meals = {}

MEALS = {
    "awake": "Are you awake bud?",
    "meal1": "🍳 Meal 1 - Breakfast: 4 scrambled eggs in butter, oats cooked with Fairlife shake, banana sliced in",
    "meal2": "🥛 Meal 2 - Mid Morning: 1.5 cups yogurt, banana, 1 tbsp honey stirred in",
    "meal3": "🍚 Meal 3 - Lunch: 1lb ground beef, 2.5 cups white rice",
    "meal4": "🍳 Meal 4 - Afternoon Snack: 3 scrambled eggs, 2 slices whole wheat toast, butter in the pan",
    "meal5": "🍗 Meal 5 - Dinner: 1.5lbs chicken breast, 2 cups white rice, 1 tbsp olive oil on rice",
    "meal6": "🍫 Meal 6 - Before Bed: 1 Fairlife shake, 1 cup Greek yogurt to finish the container",
}

TASKS = [
    ("awake", "Are you awake bud?", "08:05", 30),
    ("meal1", "🍳 Meal 1 - Breakfast: 4 scrambled eggs in butter, oats cooked with Fairlife shake, banana sliced in", "08:30", 30),
    ("water1", "💧 Drink some water!", "09:30", None),
    ("meal2", "🥛 Meal 2 - Mid Morning: 1.5 cups yogurt, banana, 1 tbsp honey stirred in", "10:30", 30),
    ("water2", "💧 Drink some water!", "11:45", None),
    ("meal3", "🍚 Meal 3 - Lunch: 1lb ground beef, 2.5 cups white rice", "13:00", 30),
    ("water3", "💧 Drink some water!", "14:30", None),
    ("meal4", "🍳 Meal 4 - Afternoon Snack: 3 scrambled eggs, 2 slices whole wheat toast, butter in the pan", "16:00", 30),
    ("water4", "💧 Drink some water!", "17:30", None),
    ("meal5", "🍗 Meal 5 - Dinner: 1.5lbs chicken breast, 2 cups white rice, 1 tbsp olive oil on rice", "19:00", 30),
    ("water5", "💧 Drink some water!", "20:15", None),
    ("meal6", "🍫 Meal 6 - Before Bed: 1 Fairlife shake, 1 cup Greek yogurt to finish the container", "21:30", 30),
]

def send_text(meal_id, message):
    if meal_id in completed_meals:
        return
    try:
        msg = MIMEText(message)
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = VERIZON_SMS_GATEWAY
        msg["Subject"] = ""
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, VERIZON_SMS_GATEWAY, msg.as_string())
        print(f"[{datetime.now().strftime('%H:%M')}] Sent: {message}")
    except Exception as e:
        print(f"Error sending text: {e}")

def reset_meals():
    completed_meals.clear()
    snoozed_meals.clear()
    print("Meals reset for new day!")

def setup_tasks():
    for meal_id, task, task_time, interval in TASKS:
        schedule.every().day.at(task_time).do(send_text, meal_id, f"⚠️ REMINDER: {task}")
        if interval is not None:
            schedule.every(interval).seconds.do(send_text, meal_id, f"🔴 STILL WAITING: {task}")
    schedule.every().day.at("00:00").do(reset_meals)

def run_scheduler():
    setup_tasks()
    print("Reminder bot is running...")
    while True:
        schedule.run_pending()
        time.sleep(30)

@app.route('/')
def index():
    return render_template('index.html', meals=MEALS)

@app.route('/verify', methods=['POST'])
def verify_meal():
    meal_id = request.form.get('meal_id')
    meal_name = MEALS.get(meal_id, "")

    if 'photo' not in request.files:
        return jsonify({"success": False, "message": "No photo uploaded"})

    file = request.files['photo']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"})

    img = Image.open(file)
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    image_data = base64.standard_b64encode(buffer.read()).decode("utf-8")
    media_type = "image/jpeg"

    if meal_id == "awake":
        prompt = "Does this photo show a person or a human face? Answer only YES or NO."
    else:
        prompt = f"Look at this photo. Does it roughly match this meal: {meal_name}? It doesn't have to be perfect but it should look similar. Answer only YES or NO."

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=64,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    response_text = message.content[0].text.strip().upper()

    if "YES" in response_text:
        completed_meals.add(meal_id)
        return jsonify({"success": True, "message": "✅ Great job Pete! Nagging stopped!"})
    else:
        return jsonify({"success": False, "message": "🤔 That doesn't look right. Try again or snooze!"})

@app.route('/snooze', methods=['POST'])
def snooze_meal():
    meal_id = request.form.get('meal_id')
    snooze_minutes = int(request.form.get('snooze_minutes', 60))
    snoozed_meals[meal_id] = snooze_minutes
    return jsonify({"success": True, "message": f"😴 Snoozed for {snooze_minutes} minutes!"})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "completed": list(completed_meals),
        "snoozed": snoozed_meals
    })

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)