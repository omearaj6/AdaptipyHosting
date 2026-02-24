from django.urls import path
from . import views
from .views_auth import register
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('recommend/', views.recommend_problem, name='recommend_problem'),
    path('', views.coding_demo, name='coding_demo'),
    path("notebook/", views.notebook_page, name="notebook_page"),
    path("register/", register, name="register"),
    path('save_notebook/', views.save_notebook, name='save_notebook'),
    
]