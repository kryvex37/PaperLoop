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
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            success_url="/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/accounts/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("institution/", views.institution_dashboard, name="institution_dashboard"),
    path("institution/profile/", views.edit_institution_profile, name="institution_profile"),
    path("ai/bulk-aggregation/", views.bulk_aggregation_dashboard, name="bulk_aggregation"),
    path("institution/partners/", views.partner_directory, name="partner_directory"),
    path("institution/partners/<int:profile_id>/", views.partner_public_detail, name="partner_public_detail"),
    path("institution/listings/new/", views.create_listing, name="listing_create"),
    path("institution/listings/<int:listing_id>/edit/", views.edit_listing, name="listing_edit"),
    path("institution/listings/<int:listing_id>/withdraw/", views.cancel_listing, name="listing_cancel"),
    path("institution/listings/<int:listing_id>/photo/", views.listing_photo, name="listing_photo"),
    path("institution/listings/<int:listing_id>/recommendations/", views.listing_recommendations, name="listing_recommendations"),
    path("institution/listings/<int:listing_id>/select-partner/", views.select_recommended_partner, name="select_recommended_partner"),
    path("partner/", views.partner_dashboard, name="partner_dashboard"),
    path("partner/profile/", views.edit_partner_profile, name="partner_profile"),
    path("partner/profile/new/", views.edit_partner_profile, name="partner_profile_create"),
    path("partner/profile/view/", views.partner_profile_detail, name="partner_profile_detail"),
    path("collections/<int:collection_id>/", views.collection_detail, name="collection_detail"),
    path("collections/<int:collection_id>/accept/", views.partner_accept_collection, name="partner_accept_collection"),
    path("collections/<int:collection_id>/reject/", views.partner_reject_collection, name="partner_reject_collection"),
    path("collections/<int:collection_id>/schedule/", views.partner_schedule_collection, name="partner_schedule_collection"),
    path("collections/<int:collection_id>/complete/", views.partner_complete_collection, name="partner_complete_collection"),
    path("collections/<int:collection_id>/cancel/", views.institution_cancel_collection, name="institution_cancel_collection"),
    path("transactions/", views.transaction_history, name="transaction_history"),
    path("transactions/<int:transaction_id>/", views.transaction_detail, name="transaction_detail"),
    path("transactions/<int:transaction_id>/record/", views.digital_record_view, name="digital_record"),
    path("about/", views.about_view, name="about"),
    path("landing/", views.landing_view, name="landing"),
    path("api/locations/divisions/", views.api_location_divisions, name="api_location_divisions"),
    path("api/locations/districts/<str:division>/", views.api_location_districts, name="api_location_districts"),
    path("api/locations/upazilas/<str:district>/", views.api_location_upazilas, name="api_location_upazilas"),
    path("api/locations/search/", views.api_location_search, name="api_location_search"),
    path("api/locations/reverse/", views.api_location_reverse, name="api_location_reverse"),
]
