

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
urlpatterns = [
    path('', views.home, name="home"),
    path('welcome/', views.public_landing, name="public_landing"),
    path('dashboard/', views.dashboard_home, name="dashboard_home"),
    path('calendar/google/', views.google_calendar, name='google_calendar'),
    path('notes/', views.notes, name="notes"),
    path('delete_note/<int:pk>/', views.delete_note, name="delete-note"), 
    path('notes_detail/<int:pk>/', views.NotesDetailView.as_view(), name="notes-detail"), 
    path('homework', views.homework, name="homework"),
    path('update_homework/<int:pk>/', views.update_homework, name="update-homework"),
    path('delete_homework/<int:pk>/',views.delete_homework,name="delete-homework"),
    path('youtube/', views.youtube , name="youtube"),
    path('youtube/watch/<str:video_id>/', views.youtube_watch, name='youtube_watch'),
    path('todo', views.todo , name="todo"),
    path('update_todo/<int:pk>/', views.update_todo, name="update-todo"),
    path('delete_todo/<int:pk>/', views.delete_todo, name="delete-todo"),
    path('books', views.books , name="books"),
    path('dictionary', views.dictionary, name="dictionary"),
    path('wiki', views.wiki , name="wiki"),
    path('conversion', views.conversion , name="conversion"),
    path('notes/', views.notes, name='notes'),
    path('notes/<int:pk>/', views.notes_detail, name='notes-detail'),
    path('setup-email-notification/', views.setup_email_notification, name='setup-email-notification'),

    
    



]    
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)