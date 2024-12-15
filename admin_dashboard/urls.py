from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('check-reservations/', views.check_reservations, name='check_reservations'),
    path('mark-as-complete/<int:reservation_id>/', views.mark_as_complete, name='mark_as_complete'),
    path('recommendation/', views.admin_recommendation, name='admin_recommendation'),
    path('export-monthly-reservations/', views.export_monthly_reservations, name='export_monthly_reservations'),
    path('edit-status/<int:reservation_id>/', views.edit_status, name='edit_status'),
    path('update-payment/<int:reservation_id>/', views.update_payment, name='update_payment'),
    path('export-recommendation-pdf/', views.export_recommendation_pdf, name='export_recommendation_pdf'),
]