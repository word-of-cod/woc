from django.urls import path
from src import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('matches/', views.matches, name='matches'),
    path(
        'refresh-betting-lines/',
        views.refresh_betting_lines,
        name='refresh_betting_lines',
    ),
]
