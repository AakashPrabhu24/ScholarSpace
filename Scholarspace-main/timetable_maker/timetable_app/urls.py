from django.urls import path
from . import views

app_name = 'timetable_app'

urlpatterns = [
    path('', views.home, name='home'),
    path('questions/', views.questions, name='questions'),
    path('generate_timetable/', views.generate_timetable, name='generate_timetable'),
]