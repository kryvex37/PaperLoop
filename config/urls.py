from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views


handler403 = "accounts.views.permission_denied"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", account_views.dashboard, name="home"),
]
