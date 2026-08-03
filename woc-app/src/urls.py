from django.urls import path
from src import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # Map the root URL to the index view
]