from django.urls import path
from . import views, notebook_views
from .views_auth import register

urlpatterns = [
    path('', views.coding_demo, name='coding_demo'),
    path("notebook/", notebook_views.notebook_page, name="notebook_page"),
    path("register/", register, name="register"),
    path('save_notebook/', notebook_views.save_notebook, name='save_notebook'),
    path('save_theme/', views.save_theme, name='save_theme'), 
]