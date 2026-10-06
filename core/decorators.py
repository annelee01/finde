from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def admin_required(view_func):
    """Restrict a view to the site admin account (settings.ADMIN_USERNAME)."""
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.username != settings.ADMIN_USERNAME:
            return HttpResponseForbidden("You do not have permission to view this page.")
        return view_func(request, *args, **kwargs)
    return wrapper
