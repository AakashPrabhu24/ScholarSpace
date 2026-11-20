import dashboard.admin  # noqa: F401 — register models + patch AdminSite.logout before admin URLs load
from dashboard import views as dash_views
from dashboard.forms import ScholarSpaceAuthenticationForm
from dashboard.google_oauth import google_oauth_callback, google_oauth_start
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("calculator/", include("calculator.urls")),
    path("quiz/", include("quiz_app.urls")),
    path("courses/", include("portal.urls", namespace="portal")),
    path("timetable/", include("timetable_app.urls")),
    path("manage-work/", include("manage_work.urls", namespace="manage_work")),
    path("register/", dash_views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="dashboard/login.html",
            authentication_form=ScholarSpaceAuthenticationForm,
        ),
        name="login",
    ),
    path("oauth/google/", google_oauth_start, name="google_oauth_start"),
    path("oauth/google/callback/", google_oauth_callback, name="google_oauth_callback"),
    path("logout/", dash_views.site_logout, name="logout"),
    path("profile/", dash_views.profile, name="profile"),
    path("", include("dashboard.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
