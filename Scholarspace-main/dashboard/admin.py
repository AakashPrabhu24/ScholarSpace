from django.contrib import admin
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect

from .models import Homework, Notes, Todo, UserProfile, Notification


def _scholarspace_admin_logout(self, request, extra_context=None):
    """Skip LogoutView (its GET renders the black 'Logged out' page); redirect to public landing."""
    auth_logout(request)
    return redirect("public_landing")


admin.AdminSite.logout = _scholarspace_admin_logout

admin.site.register(Notes)
admin.site.register(Homework)
admin.site.register(Todo)
admin.site.register(UserProfile)

admin.site.register(Notification)
