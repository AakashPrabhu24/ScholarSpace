from django.urls import path
from . import views

app_name = 'calculator'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/recognize/', views.recognize_math, name='recognize'),
    path('api/solve/', views.solve_math, name='solve'),
    path('api/graph/', views.graph_math, name='graph'),
]
