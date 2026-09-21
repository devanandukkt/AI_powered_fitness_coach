import secrets
import string
import os
import cv2
import base64
import numpy as np
import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Avg
from django.http import JsonResponse
from .exercise_model.pushup import PushupDetector
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, update_session_auth_hash, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import WorkoutSession
from .models import Profile
from .forms import (
    RegistrationForm, 
    LoginForm, 
    ForgotPasswordForm, 
    ProfileUpdateForm, 
    CustomPasswordChangeForm
)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            messages.success(request, "Account created successfully! Please log in.")
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login_input = form.cleaned_data['username_or_email']
            password = form.cleaned_data['password']

            user_obj = User.objects.filter(username=login_input).first() or \
                       User.objects.filter(email=login_input).first()

            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect('home')

            messages.error(request, "Invalid username/email or password.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def forgot_password_view(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            input_val = form.cleaned_data['username_or_email']
            
            user = User.objects.filter(username=input_val).first() or \
                   User.objects.filter(email=input_val).first()

            if user and user.email:
                alphabet = string.ascii_letters + string.digits
                temp_password = ''.join(secrets.choice(alphabet) for _ in range(10))

                user.set_password(temp_password)
                user.save()

                subject = "Your Temporary Password - AI_Fit"
                message = (
                    f"Hello {user.username},\n\n"
                    f"We received a request to reset your password for your AI_Fit account.\n\n"
                    f"Your temporary password is: {temp_password}\n\n"
                    f"Please log in using this temporary password and change it immediately from your profile.\n\n"
                    f"Best regards,\n"
                    f"The AI_Fit Team"
                )

                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    messages.success(request, f"A temporary password has been sent to {user.email}.")
                    return redirect('login')
                except Exception as e:
                    messages.error(request, f"Error sending email: {e}")
            else:
                messages.error(request, "No account found with that username or email.")
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forget.html', {'form': form})


@login_required
def home_view(request):
    # Use local date to avoid UTC date mismatch issues
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)

    # 1. Fetch Today's Workouts for the user
    todays_workouts = WorkoutSession.objects.filter(
        user=request.user, 
        created_at__date=today
    )

    # 2. Calorie Burn (Past 7 Days)
    date_labels = []
    calories_data = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        date_labels.append(day.strftime("%b %d"))
        
        daily_cals = WorkoutSession.objects.filter(
            user=request.user, 
            created_at__date=day
        ).aggregate(total=Sum('calories'))['total'] or 0
        
        calories_data.append(daily_cals)

    # 3. Today's Exercise Breakdown
    # Ensure these keys match EXACTLY what is saved in your WorkoutHistory model's exercise_type field!
    exercise_keys = ['pushup', 'situp', 'squat'] 
    exercise_labels = ['Push Up', 'Sit Up', 'Squat']
    
    exercise_counts = []
    exercise_accuracies = []

    for key in exercise_keys:
        # Filter using __iexact to ignore case sensitivity issues (e.g., "Pushup" vs "pushup")
        stats = todays_workouts.filter(exercise_type__iexact=key).aggregate(
            total_reps=Sum('count'),
            avg_acc=Avg('accuracy')
        )
        
        exercise_counts.append(stats['total_reps'] or 0)
        exercise_accuracies.append(round(stats['avg_acc'] or 0, 1))

    # Pass serialized JSON strings to template
    context = {
        'todays_workouts': todays_workouts,
        'date_labels_json': json.dumps(date_labels),
        'calories_data_json': json.dumps(calories_data),
        'exercise_types_json': json.dumps(exercise_labels),
        'exercise_counts_json': json.dumps(exercise_counts),
        'exercise_accuracies_json': json.dumps(exercise_accuracies),
    }

    return render(request, 'accounts/home.html', context)

@login_required(login_url='login')
def profile_view(request):
    return render(request, 'accounts/profile.html')


@never_cache
def logout_view(request):
    logout(request)
    messages.info(request, "You have logged out successfully.")
    return redirect('login')


@login_required(login_url='login')
def edit_profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your personal details have been updated!")
            return redirect('profile')
        else:
            messages.error(request, "Please fix the errors in the form below.")
    else:
        form = ProfileUpdateForm(instance=profile)
    return render(request, 'accounts/edit_profile.html', {'form': form})


@login_required(login_url='login')
def change_password_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        # else:
        #     messages.error(request, 'Please correct the password requirements below.')
    else:
        form = CustomPasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})


@never_cache
@login_required(login_url='login')
def delete_user_view(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been deleted successfully.")
        return redirect('login')
    return render(request, 'accounts/delete_account.html')


@never_cache
@login_required(login_url='login')
def exercise_view(request):
    exercise_type = request.GET.get('exercise_type', 'pushup')
    
    # Format string for display (e.g., "pushup" -> "Push Up")
    display_name = exercise_type.replace('_', ' ').title()

    context = {
        'exercise_type': exercise_type,
        'display_name': display_name,
    }
    return render(request, 'accounts/exercise.html', context)



pushup_detector = PushupDetector()

RECORDINGS_DIR = os.path.join(settings.BASE_DIR, 'static', 'recordings')
os.makedirs(RECORDINGS_DIR, exist_ok=True)

SESSION_DATA = {
    'counter': 0,
    'total_attempts': 0,
    'stage': None,
    'bad_form_flag': False,
    'top_shoulder_y': None,
    'video_writer': None,
    'video_filename': 'recorded_feedback.mp4'
}

@csrf_exempt
def start_exercise_session(request):
    global SESSION_DATA
    if SESSION_DATA['video_writer'] is not None:
        SESSION_DATA['video_writer'].release()

    SESSION_DATA.update({
        'counter': 0,
        'total_attempts': 0,
        'stage': None,
        'bad_form_flag': False,
        'top_shoulder_y': None,
        'video_writer': None
    })
    return JsonResponse({'status': 'started'})

@csrf_exempt
def process_exercise_frame(request):
    global SESSION_DATA
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    image_data = request.POST.get('image')
    if not image_data:
        return JsonResponse({'error': 'No image data'}, status=400)

    encoded_data = image_data.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return JsonResponse({'error': 'Invalid image'}, status=400)

    h, w, _ = img.shape

    if SESSION_DATA['video_writer'] is None:
        filepath = os.path.join(RECORDINGS_DIR, SESSION_DATA['video_filename'])
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        SESSION_DATA['video_writer'] = cv2.VideoWriter(filepath, fourcc, 12.0, (w, h))

    # Delegate processing to pushup_detector module
    img, counter, accuracy, calories_burned = pushup_detector.process_frame(img, SESSION_DATA)

    if SESSION_DATA['video_writer'] is not None:
        SESSION_DATA['video_writer'].write(img)

    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    frame_bytes = base64.b64encode(buffer).decode('utf-8')

    return JsonResponse({
        'image': f"data:image/jpeg;base64,{frame_bytes}",
        'count': counter,
        'accuracy': accuracy,
        'calories': calories_burned
    })

@csrf_exempt
def stop_exercise_session(request):
    global SESSION_DATA
    
    # Save the current results before resetting
    final_count = SESSION_DATA['counter']
    final_attempts = SESSION_DATA['total_attempts']
    
    # Stop video writer
    if SESSION_DATA['video_writer'] is not None:
        SESSION_DATA['video_writer'].release()
        SESSION_DATA['video_writer'] = None

    # Reset backend tracking state
    SESSION_DATA.update({
        'counter': 0,
        'total_attempts': 0,
        'stage': None,
        'bad_form_flag': False,
        'top_shoulder_y': None,
    })

    video_url = f"{settings.STATIC_URL}recordings/{SESSION_DATA['video_filename']}"
    return JsonResponse({
        'status': 'reset_complete',
        'video_url': video_url,
        'saved_reps': final_count
    })


@csrf_exempt
def save_workout_session(request):
    """
    Saves a new exercise session to the database under the user's ID.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST request required'}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Please log in to save workout.'}, status=401)

    try:
        data = json.loads(request.body)

        # Create record linked to request.user.id
        workout = WorkoutSession.objects.create(
            user=request.user, # Assigns user and stores user_id in DB
            exercise_type=data.get('exercise_type', 'Exercise'),
            count=int(data.get('count', 0)),
            accuracy=float(data.get('accuracy', 0.0)),
            calories=float(data.get('calories', 0.0))
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Workout saved!',
            'user_id': workout.user.id,
            'date': workout.created_at.strftime('%Y-%m-%d'),
            'time': workout.created_at.strftime('%H:%M:%S')
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# views.py
@login_required
def user_dashboard(request):
    user_workouts = WorkoutSession.objects.filter(user=request.user)
    return render(request, 'dashboard.html', {'workouts': user_workouts})