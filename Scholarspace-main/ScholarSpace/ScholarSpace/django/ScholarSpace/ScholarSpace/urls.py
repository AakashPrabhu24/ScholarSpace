import dashboard.admin  # noqa: F401 — register models + patch AdminSite.logout before admin URLs load

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views as dash_views
from dashboard.forms import ScholarSpaceAuthenticationForm
from dashboard.google_oauth import google_oauth_callback, google_oauth_start
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('timetable/', include('timetable_app.urls')),
    path('', include('dashboard.urls')),
    path('register/', dash_views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='dashboard/login.html',
            authentication_form=ScholarSpaceAuthenticationForm,
        ),
        name='login',
    ),
    path('oauth/google/', google_oauth_start, name='google_oauth_start'),
    path('oauth/google/callback/', google_oauth_callback, name='google_oauth_callback'),
    path('logout/', dash_views.site_logout, name='logout'),
    path('profile/', dash_views.profile, name='profile'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)