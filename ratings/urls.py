from django.urls import path
from . import views

app_name = 'ratings'

urlpatterns = [
    path('create/', views.create_rating, name='create_rating'),
    path('view/', views.view_ratings, name='view_ratings'),
    path('edit/<int:rating_id>/', views.edit_rating, name='edit_rating'),
    path('check-user-rating/', views.check_user_rating, name='check_user_rating'),
]