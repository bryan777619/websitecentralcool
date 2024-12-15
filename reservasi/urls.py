from django.urls import path

from . import views

urlpatterns = [
    path("", views.home),
    path('buat-reservasi/', views.buat_reservasi, name='buat_reservasi'),
    path('riwayat-reservasi/', views.riwayat_reservasi, name='riwayat_reservasi'),
    path('get_recommendation/', views.get_recommendation, name='get_recommendation'),
    path('batalkan-reservasi/<int:reservasi_id>/', views.batalkan_reservasi, name='batalkan_reservasi'),
    path('export-recommendation/<int:recommendation_id>/', views.export_recommendation_pdf, name='export_recommendation_pdf'),
]