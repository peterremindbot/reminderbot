from flask import Flask, render_template, request, jsonify
import anthropic
import base64
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Track completed meals and snoozes
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

    # Read and encode the image
    image_data = base64.standard_b64encode(file.read()).decode("utf-8")
    media_type = file.content_type

    # Use Claude to verify the meal
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
                        "text": f"Look at this photo. Does it show food or a meal? I need to eat: {meal_name}. Answer only YES or NO."
                    }
                ],
            }
        ],
    )

    response_text = message.content[0].text.strip().upper()

    if "YES" in response_text:
        completed_meals.add(meal_id)
        return jsonify({"success": True, "message": f"✅ Great job Pete! Meal marked done!"})
    else:
        return jsonify({"success": False, "message": "🤔 Doesn't look like food. Try again or snooze!"})

@app.route('/snooze', methods=['POST'])
def snooze_meal():
    meal_id = request.form.get('meal_id')
    snooze_minutes = int(request.form.get('snooze_minutes', 60))
    snoozed_meals[meal_id] = snooze_minutes
    return jsonify({"success": True, "message": f"😴 Snoozed for {snooze_minutes} minutes! I'll remind you again then."})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "completed": list(completed_meals),
        "snoozed": snoozed_meals
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)