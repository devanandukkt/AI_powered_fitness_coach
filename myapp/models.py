from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=100, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    height = models.FloatField(help_text="Height in cm", blank=True, null=True)
    weight = models.FloatField(help_text="Weight in kg", blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class WorkoutSession(models.Model):
    # Foreign key links each record directly to the user's ID
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workouts')
    exercise_type = models.CharField(max_length=50)
    count = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    calories = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] # Shows newest workouts first

    def __str__(self):
        return f"User ID: {self.user.id} ({self.user.username}) - {self.exercise_type} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Automatically create or update Profile when User is created/updated
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)