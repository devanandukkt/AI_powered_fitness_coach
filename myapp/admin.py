from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from .models import Profile
from .models import WorkoutSession

try:
    admin.site.register(Profile)
except AlreadyRegistered:
    pass

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    # Includes user_id explicitly in the admin list view
    list_display = ('user_id_display', 'user', 'exercise_type', 'count', 'accuracy', 'calories', 'created_at')
    list_filter = ('exercise_type', 'created_at', 'user')
    search_fields = ('user__username', 'user__id', 'exercise_type')

    def user_id_display(self, obj):
        return obj.user.id
    user_id_display.short_description = 'User ID'