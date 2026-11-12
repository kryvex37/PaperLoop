from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .forms import RegistrationForm
from .models import UserRole


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(
            request,
            "Your PaperLoop account has been created. You can now sign in.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    if request.user.role == UserRole.EDUCATIONAL_INSTITUTION:
        return redirect("accounts:institution_dashboard")
    if request.user.role == UserRole.RECYCLING_PARTNER:
        return redirect("accounts:partner_dashboard")
    return render(request, "accounts/access_unavailable.html", status=403)


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def institution_dashboard(request):
    return render(request, "accounts/institution_dashboard.html")


@role_required(UserRole.RECYCLING_PARTNER)
def partner_dashboard(request):
    return render(request, "accounts/partner_dashboard.html")


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
