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
import pytz
from datetime import datetime
import os
from datetime import datetime
import pytz

def get_local_time():
    mountain = pytz.timezone('America/Denver')
    return datetime.now(mountain)

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
snooze_counts = {}
streak = 0
paused = False

MEALS = {
    "awake": "Are you awake bud?",
    "meal1": "🍳 Meal 1 - Breakfast: 4 scrambled eggs in butter, oats cooked with Fairlife shake, banana sliced in",
    "meal2": "🥛 Meal 2 - Mid Morning: 1.5 cups yogurt, banana, 1 tbsp honey stirred in",
    "meal3": "🍚 Meal 3 - Lunch: 1lb ground beef, 2.5 cups white rice",
    "meal4": "🍳 Meal 4 - Afternoon Snack: 3 scrambled eggs, 2 slices whole wheat toast, butter in the pan",
    "meal5": "🍗 Meal 5 - Dinner: 1.5lbs chicken breast, 2 cups white rice, 1 tbsp olive oil on rice",
    "meal6": "🍫 Meal 6 - Before Bed: 1 Fairlife shake, 1 cup Greek yogurt to finish the container",
}

WEEKDAY_TASKS = [
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

WEEKEND_TASKS = [
    ("awake", "Are you awake bud?", "09:05", 30),
    ("meal1", "🍳 Meal 1 - Breakfast: 4 scrambled eggs in butter, oats cooked with Fairlife shake, banana sliced in", "09:30", 30),
    ("water1", "💧 Drink some water!", "10:30", None),
    ("meal2", "🥛 Meal 2 - Mid Morning: 1.5 cups yogurt, banana, 1 tbsp honey stirred in", "11:30", 30),
    ("water2", "💧 Drink some water!", "12:45", None),
    ("meal3", "🍚 Meal 3 - Lunch: 1lb ground beef, 2.5 cups white rice", "14:00", 30),
    ("water3", "💧 Drink some water!", "15:30", None),
    ("meal4", "🍳 Meal 4 - Afternoon Snack: 3 scrambled eggs, 2 slices whole wheat toast, butter in the pan", "17:00", 30),
    ("water4", "💧 Drink some water!", "18:30", None),
    ("meal5", "🍗 Meal 5 - Dinner: 1.5lbs chicken breast, 2 cups white rice, 1 tbsp olive oil on rice", "20:00", 30),
    ("water5", "💧 Drink some water!", "21:15", None),
    ("meal6", "🍫 Meal 6 - Before Bed: 1 Fairlife shake, 1 cup Greek yogurt to finish the container", "22:30", 30),
]

DATA_FILE = "data.json"

def save_data():
    import json
    with open(DATA_FILE, "w") as f:
        json.dump({
            "streak": streak,
            "completed_meals": list(completed_meals),
            "last_saved": datetime.now().strftime("%Y-%m-%d"),
            "custom_tasks": custom_tasks
        }, f)

def load_data():
    global streak, completed_meals, custom_tasks
    try:
        import json
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            streak = data.get("streak", 0)
            saved_date = data.get("last_saved", "")
            today = datetime.now().strftime("%Y-%m-%d")
            if saved_date == today:
                completed_meals = set(data.get("completed_meals", []))
            else:
                completed_meals = set()
            custom_tasks = data.get("custom_tasks", [])
        print(f"Loaded data — streak: {streak}")
    except FileNotFoundError:
        print("No save file found, starting fresh!")

custom_tasks = []

def send_text(meal_id, message):
    if paused:
        return
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

def send_motivational_message():
    done_count = len([m for m in completed_meals if not m.startswith("water")])
    total = 7
    if done_count == 0:
        msg = "💬 Hey Pete, you haven't checked off anything yet today. Let's get moving!"
    elif done_count <= 2:
        msg = f"💬 {done_count}/{total} meals done. You're just getting started — keep going!"
    elif done_count <= 4:
        msg = f"💬 {done_count}/{total} meals down. You're halfway there Pete, don't stop now!"
    elif done_count <= 6:
        msg = f"💬 {done_count}/{total} meals done. Almost there, finish strong!"
    else:
        msg = "💬 All meals done! You're an absolute machine Pete! 💪"
    send_text("motivation", msg)

def send_daily_summary():
    global streak
    meal_list = {
        "awake": "Wake up check",
        "meal1": "Breakfast",
        "meal2": "Mid Morning",
        "meal3": "Lunch",
        "meal4": "Afternoon Snack",
        "meal5": "Dinner",
        "meal6": "Before Bed",
    }
    done = [name for meal_id, name in meal_list.items() if meal_id in completed_meals]
    missed = [name for meal_id, name in meal_list.items() if meal_id not in completed_meals]

    if len(done) == 7:
        streak += 1
    else:
        streak = 0

    save_data()

    summary = "📊 Daily Summary\n"
    summary += f"✅ Done ({len(done)}/7):\n"
    for item in done:
        summary += f"  • {item}\n"
    if missed:
        summary += f"❌ Missed ({len(missed)}/7):\n"
        for item in missed:
            summary += f"  • {item}\n"
    if len(done) == 7:
        summary += f"\n🏆 Perfect day Pete! Streak: {streak} day{'s' if streak > 1 else ''}!"
    elif len(done) >= 5:
        summary += "\n💪 Solid day, keep it up!"
    else:
        summary += "\n😤 Do better tomorrow Pete!"

    if streak > 0:
        summary += f"\n🔥 Current streak: {streak} day{'s' if streak > 1 else ''}"

    send_text("summary", summary)

def send_streak_update():
    if streak > 0:
        send_text("streak", f"🔥 Good morning Pete! You're on a {streak} day streak! Don't break it!")

def reset_meals():
    completed_meals.clear()
    snoozed_meals.clear()
    snooze_counts.clear()
    print("Meals reset for new day!")

def schedule_custom_tasks():
    for task in custom_tasks:
        task_id = task["id"]
        task_name = task["name"]
        task_time = task["time"]
        interval = task.get("interval", None)
        schedule.every().day.at(task_time).do(send_text, task_id, f"⚠️ REMINDER: {task_name}")
        if interval:
            schedule.every(interval).seconds.do(send_text, task_id, f"🔴 STILL WAITING: {task_name}")

def setup_tasks():
    schedule.clear()
    today = datetime.now().weekday()
    tasks = WEEKEND_TASKS if today >= 5 else WEEKDAY_TASKS
    for meal_id, task, task_time, interval in tasks:
        schedule.every().day.at(task_time).do(send_text, meal_id, f"⚠️ REMINDER: {task}")
        if interval is not None:
            schedule.every(interval).seconds.do(send_text, meal_id, f"🔴 STILL WAITING: {task}")
    schedule.every().day.at("14:00").do(send_motivational_message)
    schedule.every().day.at("22:00").do(send_daily_summary)
    schedule.every().day.at("00:00").do(reset_meals)
    schedule.every().day.at("08:00").do(send_streak_update)
    schedule_custom_tasks()

def run_scheduler():
    load_data()
    schedule.clear()
    setup_tasks()
    print(f"Reminder bot is running... Current time: {datetime.now().strftime('%H:%M')}")
    while True:
        schedule.run_pending()
        time.sleep(30)

@app.route('/')
def index():
    return render_template('index.html', meals=MEALS, custom_tasks=custom_tasks)

@app.route('/pause', methods=['POST'])
def pause_bot():
    global paused
    paused = not paused
    status = "paused" if paused else "resumed"
    return jsonify({"success": True, "paused": paused, "message": f"Bot {status}!"})

@app.route('/add_task', methods=['POST'])
def add_task():
    import uuid
    task_name = request.form.get('task_name')
    task_time = request.form.get('task_time')
    nag = request.form.get('nag') == 'true'

    if not task_name or not task_time:
        return jsonify({"success": False, "message": "Task name and time are required!"})

    task_id = "custom_" + str(uuid.uuid4())[:8]
    task = {
        "id": task_id,
        "name": task_name,
        "time": task_time,
        "interval": 30 if nag else None
    }
    custom_tasks.append(task)
    MEALS[task_id] = task_name
    schedule.every().day.at(task_time).do(send_text, task_id, f"⚠️ REMINDER: {task_name}")
    if nag:
        schedule.every(30).seconds.do(send_text, task_id, f"🔴 STILL WAITING: {task_name}")
    save_data()
    return jsonify({"success": True, "message": f"Task added!", "task": task})

@app.route('/remove_task', methods=['POST'])
def remove_task():
    task_id = request.form.get('task_id')
    global custom_tasks
    custom_tasks = [t for t in custom_tasks if t["id"] != task_id]
    if task_id in MEALS:
        del MEALS[task_id]
    save_data()
    return jsonify({"success": True, "message": "Task removed!"})

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
        prompt = f"Look at this photo. Does it roughly match this meal or task: {meal_name}? Answer only YES or NO."

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
        save_data()
        return jsonify({"success": True, "message": "✅ Great job Pete! Nagging stopped!"})
    else:
        return jsonify({"success": False, "message": "🤔 That doesn't look right. Try again or snooze!"})

@app.route('/snooze', methods=['POST'])
def snooze_meal():
    meal_id = request.form.get('meal_id')
    snooze_minutes = int(request.form.get('snooze_minutes', 60))

    snooze_counts[meal_id] = snooze_counts.get(meal_id, 0) + 1
    snoozed_meals[meal_id] = snooze_minutes

    if snooze_counts[meal_id] > 1:
        meal_name = MEALS.get(meal_id, "your meal")
        roast_message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": f"Give me a short funny roast (1-2 sentences max) for someone who has snoozed their reminder to eat {meal_name} {snooze_counts[meal_id]} times. Be playful not mean."
                }
            ],
        )
        roast = roast_message.content[0].text.strip()
        threading.Thread(target=send_text, args=(meal_id + "_roast", f"🔥 {roast}")).start()

    return jsonify({"success": True, "message": f"😴 Snoozed for {snooze_minutes} minutes!"})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "completed": list(completed_meals),
        "snoozed": snoozed_meals,
        "streak": streak,
        "paused": paused
    })

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)