from django.utils.cache import add_never_cache_headers
from django.utils import timezone

from .models import LoginActivityDay


class LoginActivityMiddleware:
    """Record one activity date for each authenticated user per local day."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            LoginActivityDay.objects.get_or_create(
                user=request.user,
                date=timezone.localdate(),
            )
        return self.get_response(request)


class NoCacheMiddleware:
    """
    Prevents browser from caching pages for authenticated users.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
