from django.urls import path
from . import views
from .views_auth import register
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('recommend/', views.recommend_problem, name='recommend_problem'),
    path('', views.coding_demo, name='coding_demo'),
    path("register/", register, name="register")
]