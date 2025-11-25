from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('livestream/', views.livestream, name='livestream'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('tabel/', views.tabel_pelanggaran, name='tabel_pelanggaran'),

    # ACTION
    path('delete/<int:id>/', views.delete_pelanggaran, name='delete_pelanggaran'),
    path('export/<int:id>/', views.export_pdf, name='export_pdf'),
    path('logout/', views.logout_user, name='logout'),
]
