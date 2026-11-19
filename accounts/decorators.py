from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import UserRole, VerificationStatus


def role_required(*roles):
    """Require an authenticated user with one of the specified organization roles."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role not in roles:
                raise PermissionDenied
            if request.user.verification_status != VerificationStatus.VERIFIED:
                raise PermissionDenied("Your organization must be verified before using this feature.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def partner_profile_required(view_func):
    """Require an authenticated, verified partner to manage their own profile."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if (
            request.user.role != UserRole.RECYCLING_PARTNER
            or request.user.verification_status != VerificationStatus.VERIFIED
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
