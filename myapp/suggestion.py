# suggestion.py

from google import genai
from django.conf import settings
from .models import UserBMI, WorkoutSession
from datetime import datetime, timedelta

def get_user_fitness_context(user):
    latest_bmi = UserBMI.objects.filter(user=user).first()
    bmi_val = latest_bmi.bmi if latest_bmi else "Not recorded"

    week_ago = datetime.now() - timedelta(days=7)
    workouts = WorkoutSession.objects.filter(user=user, created_at__gte=week_ago)

    summary_data = []
    for w in workouts:
        summary_data.append(
            f"- {w.exercise_type}: {w.count} reps, {w.accuracy}% accuracy, {w.calories} kcal burned on {w.created_at.strftime('%b %d')}"
        )

    context_str = f"User BMI: {bmi_val}\nRecent Workouts (Past 7 Days):\n" + "\n".join(summary_data)
    return context_str

def call_gemini_single_try(client, prompt):
    # Single attempt without tenacity retry logic
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text