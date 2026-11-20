# portal/urls.py
from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    # Home page - list of domains
    path('', views.home_view, name='home'),
    
    # Domain detail - list of categories in a domain
    path('<slug:domain_slug>/', views.domain_detail_view, name='domain_detail'),
    
    # Category detail - list of subjects in a category
    path('<slug:domain_slug>/<slug:category_slug>/', 
         views.category_detail_view, 
         name='category_detail'),
    
    # Subject detail - list of videos in a subject
    path('<slug:domain_slug>/<slug:category_slug>/<slug:subject_slug>/', 
         views.subject_detail_view, 
         name='subject_detail'),
    
    # Video detail - play a specific video
    path('<slug:domain_slug>/<slug:category_slug>/<slug:subject_slug>/<slug:video_slug>/', 
         views.video_detail_view, 
         name='video_detail'),     
]