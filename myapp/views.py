import secrets
import string
import os
import cv2
import base64
import time
import glob
import subprocess
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



RECORDINGS_DIR = os.path.join(settings.BASE_DIR, 'static', 'recordings')
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# In-memory session tracking keyed by user or session
USER_SESSIONS = {}


def get_session_key(request):
    """Returns a unique string for the active user or browser session."""
    if request.user.is_authenticated:
        return f"user_{request.user.id}"
    if not request.session.session_key:
        request.session.create()
    return f"session_{request.session.session_key}"


def cleanup_user_recordings(key):
    """Deletes all previously recorded video files for this user to save disk space."""
    try:
        pattern = os.path.join(RECORDINGS_DIR, f"recording_{key}_*")
        for filepath in glob.glob(pattern):
            if os.path.exists(filepath):
                os.remove(filepath)
    except Exception as e:
        print(f"Error cleaning up old recordings for {key}: {e}")


def convert_to_h264(input_path, output_path):
    """
    Converts raw OpenCV MP4 into browser-compatible H.264 HTML5 video.
    Falls back gracefully if ffmpeg is not installed on the system.
    """
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vcodec', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'baseline',
            '-level', '3.0',
            output_path
        ]
        # Run conversion silently
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(input_path):
            os.remove(input_path)  # Delete raw file
        return True
    except Exception as e:
        print(f"FFmpeg conversion skipped or failed (using raw file): {e}")
        return False


# views.py

# views.py

@csrf_exempt
def start_exercise_session(request):
    key = get_session_key(request)

    # 1. Close existing VideoWriter if active
    if key in USER_SESSIONS and USER_SESSIONS[key].get('video_writer'):
        try:
            USER_SESSIONS[key]['video_writer'].release()
        except Exception:
            pass

    # 2. Delete old recordings for this user
    cleanup_user_recordings(key)

    filename_raw = f"recording_{key}_{int(time.time())}_raw.mp4"

    # Initialize session state with start timestamp
    USER_SESSIONS[key] = {
        'counter': 0,
        'total_attempts': 0,
        'stage': None,
        'bad_form_flag': False,
        'top_shoulder_y': None,
        'video_writer': None,
        'video_filename_raw': filename_raw,
        'detector': PushupDetector(),
        'start_time': time.time(),      # Capture exact start time
        'last_frame_time': time.time(), # Capture last frame arrival time
        'frame_count': 0
    }

    return JsonResponse({'status': 'started'})


@csrf_exempt
def process_exercise_frame(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    key = get_session_key(request)
    if key not in USER_SESSIONS:
        start_exercise_session(request)

    session_data = USER_SESSIONS[key]

    image_data = request.POST.get('image')
    if not image_data:
        return JsonResponse({'error': 'No image data'}, status=400)

    try:
        encoded_data = image_data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        return JsonResponse({'error': f'Image decode error: {str(e)}'}, status=400)

    if img is None:
        return JsonResponse({'error': 'Invalid image'}, status=400)

    h, w, _ = img.shape

    # Update last frame timestamp
    session_data['last_frame_time'] = time.time()

    # Initialize VideoWriter (recorded at base 10 FPS)
    if session_data['video_writer'] is None:
        filepath = os.path.join(RECORDINGS_DIR, session_data['video_filename_raw'])
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
        except Exception:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        session_data['video_writer'] = cv2.VideoWriter(filepath, fourcc, 10.0, (w, h))

    # Process frame
    detector = session_data['detector']
    processed_img, counter, accuracy, calories_burned = detector.process_frame(img, session_data)

    if session_data['video_writer'] is not None:
        session_data['video_writer'].write(processed_img)
        session_data['frame_count'] += 1

    _, buffer = cv2.imencode('.jpg', processed_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    frame_bytes = base64.b64encode(buffer).decode('utf-8')

    return JsonResponse({
        'image': f"data:image/jpeg;base64,{frame_bytes}",
        'count': counter,
        'accuracy': accuracy,
        'calories': calories_burned
    })


def convert_to_h264_exact_duration(input_path, output_path, total_frames, target_duration):
    """
    Converts raw video into browser H.264 video and stretches/compresses playback time
    so the final video duration matches target_duration exactly.
    """
    try:
        # Base raw video duration created by OpenCV at 10.0 FPS
        raw_duration = max(total_frames / 10.0, 0.1)
        
        # Multiply pts (presentation timestamp) by factor to force target real-world duration
        pts_factor = target_duration / raw_duration

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-filter:v', f'setpts={pts_factor}*PTS',
            '-vcodec', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'baseline',
            '-level', '3.0',
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(input_path):
            os.remove(input_path)  # Remove raw intermediate file
        return True
    except Exception as e:
        print(f"FFmpeg conversion error: {e}")
        return False


@csrf_exempt
def stop_exercise_session(request):
    key = get_session_key(request)

    if key not in USER_SESSIONS:
        return JsonResponse({'status': 'no_active_session', 'saved_reps': 0})

    session_data = USER_SESSIONS[key]
    final_count = session_data.get('counter', 0)
    raw_filename = session_data.get('video_filename_raw', '')
    raw_filepath = os.path.join(RECORDINGS_DIR, raw_filename)

    # Calculate exact duration between frame stream start and end
    start_time = session_data.get('start_time', time.time())
    end_time = session_data.get('last_frame_time', time.time())
    total_frames = session_data.get('frame_count', 0)
    
    # Real-world elapsed duration in seconds
    exact_duration = max(end_time - start_time, 1.0)

    # 1. Properly release video writer
    if session_data.get('video_writer') is not None:
        session_data['video_writer'].release()
        session_data['video_writer'] = None

    final_filename = raw_filename

    # 2. Convert and time-stretch video to match exact session duration
    if os.path.exists(raw_filepath) and total_frames > 0:
        converted_filename = raw_filename.replace('_raw.mp4', '.mp4')
        converted_filepath = os.path.join(RECORDINGS_DIR, converted_filename)
        
        if convert_to_h264_exact_duration(raw_filepath, converted_filepath, total_frames, exact_duration):
            final_filename = converted_filename

    # Clean up session dictionary
    del USER_SESSIONS[key]

    video_url = f"{settings.STATIC_URL}recordings/{final_filename}"

    return JsonResponse({
        'status': 'reset_complete',
        'video_url': video_url,
        'saved_reps': final_count
    })

@csrf_exempt
def save_workout_session(request):
    """Saves workout to database and deletes the session's recorded video file."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST request required'}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Please log in to save workout.'}, status=401)

    key = get_session_key(request)

    try:
        data = json.loads(request.body)

        workout = WorkoutSession.objects.create(
            user=request.user,
            exercise_type=data.get('exercise_type', 'Exercise'),
            count=int(data.get('count', 0)),
            accuracy=float(data.get('accuracy', 0.0)),
            calories=float(data.get('calories', 0.0))
        )

        # DELETE RECORDINGS AFTER SAVING WORKOUT to prevent disk inflation
        cleanup_user_recordings(key)

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