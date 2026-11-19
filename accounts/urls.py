from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import EmailAuthenticationForm
from . import views


app_name = "accounts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("institution/", views.institution_dashboard, name="institution_dashboard"),
    path("institution/listings/new/", views.create_listing, name="listing_create"),
    path("institution/listings/<int:listing_id>/edit/", views.edit_listing, name="listing_edit"),
    path("institution/listings/<int:listing_id>/withdraw/", views.cancel_listing, name="listing_cancel"),
    path("institution/listings/<int:listing_id>/photo/", views.listing_photo, name="listing_photo"),
    path("partner/", views.partner_dashboard, name="partner_dashboard"),
]
