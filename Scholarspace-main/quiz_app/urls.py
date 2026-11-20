from django.urls import path
from . import views

app_name = 'quiz_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),
    path('quiz/create/', views.create_quiz, name='create_quiz'),
    path('quiz/<int:quiz_id>/question/add/', views.add_question, name='add_question'),
]
