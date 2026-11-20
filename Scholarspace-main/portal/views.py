from django.shortcuts import render

from django.shortcuts import render, get_object_or_404
from .models import Domain, Category, Subject, Video

def home_view(request):
    """
    Home page view to display all domains
    """
    domains = Domain.objects.all()
    return render(request, 'portal/home.html', {
        'domains': domains
    })

def domain_detail_view(request, domain_slug):
    """
    View to display categories for a specific domain
    """
    domain = get_object_or_404(Domain, slug=domain_slug)
    categories = domain.categories.all()
    return render(request, 'portal/domain_detail.html', {
        'domain': domain,
        'categories': categories
    })

def category_detail_view(request, domain_slug, category_slug):
    """
    View to display subjects for a specific category
    """
    category = get_object_or_404(Category, 
                                 slug=category_slug, 
                                 domain__slug=domain_slug)
    subjects = category.subjects.all()
    return render(request, 'portal/category_detail.html', {
        'category': category,
        'subjects': subjects
    })

def subject_detail_view(request, domain_slug, category_slug, subject_slug):
    """
    View to display videos for a specific subject
    """
    subject = get_object_or_404(Subject, 
                                slug=subject_slug, 
                                category__slug=category_slug,
                                category__domain__slug=domain_slug)
    videos = subject.videos.all()
    return render(request, 'portal/subject_detail.html', {
        'subject': subject,
        'videos': videos
    })

def video_detail_view(request, domain_slug, category_slug, subject_slug, video_slug):
    """
    View to play a specific video
    """
    video = get_object_or_404(Video, 
                               slug=video_slug, 
                               subject__slug=subject_slug,
                               subject__category__slug=category_slug,
                               subject__category__domain__slug=domain_slug)
    return render(request, 'portal/video_detail.html', {
        'video': video
    })