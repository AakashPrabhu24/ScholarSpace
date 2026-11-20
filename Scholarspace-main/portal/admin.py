from django.contrib import admin

from django.contrib import admin
from .models import Domain, Category, Subject, Video

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'slug', 'video_count')
    list_filter = ('domain',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug', 'video_count')
    list_filter = ('category__domain', 'category')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'instructor', 'published_date', 'duration')
    list_filter = ('subject__category', 'subject', 'published_date')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'description', 'instructor')
