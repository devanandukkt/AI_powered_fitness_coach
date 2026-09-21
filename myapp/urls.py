from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('profile/', views.profile_view, name='profile'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password_view, name='forget_password'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    path('profile/delete/', views.delete_user_view, name='delete_user'),
    path('exercise/', views.exercise_view, name='exercise'),
    path('exercise/', views.exercise_view, name='exercise'),
    path('exercise/start/', views.start_exercise_session, name='start_exercise'),
    path('exercise/process/', views.process_exercise_frame, name='process_exercise_frame'),
    path('exercise/stop/', views.stop_exercise_session, name='stop_exercise'),
    path('save-workout/', views.save_workout_session, name='save_workout'),
]