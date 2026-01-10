from django.urls import path
from . import views

urlpatterns = [
    path('recommend/', views.recommend_problem, name='recommend_problem'),
    path('', views.coding_demo, name='coding_demo'),
]