from django.urls import path
from . import views


urlpatterns = [
    # =============================
    # HALAMAN UTAMA & DASAR
    # =============================
    path('', views.home, name='home'),
    path('livestream/', views.livestream, name='livestream'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('livestream-dashboard/', views.livestream_dashboard, name='livestream_dashboard'),
    path('setting/', views.setting_page, name='setting'),

    # =============================
    # DATA PELANGGARAN
    # =============================
    path('tabel/', views.tabel_pelanggaran, name='tabel_pelanggaran'),
    path('delete/<int:id>/', views.delete_pelanggaran, name='delete_pelanggaran'),
    path('export/<int:id>/', views.export_pdf, name='export_pdf'),

    # =============================
    # AUTENTIKASI
    # =============================
    path('logout/', views.logout_user, name='logout'),

    # =============================
    # API UNTUK YOLO & REALTIME DASHBOARD
    # =============================

    # versi lama (dipertahankan untuk kompatibilitas)
    path('api/yolo-test/', views.yolo_test, name='yolo_test'),

    # endpoint pengiriman data terbaru ke dashboard frontend
    path('api/yolo-data/', views.get_yolo_data, name='get_yolo_data'),

    # versi baru (placeholder untuk pengembangan selanjutnya)
    # pastikan belum diaktifkan karena views.yolo_get_data belum dibuat
    # path('api/yolo-receive/', views.yolo_receive_data, name='yolo_receive_data'),
    # path('api/yolo-get/', views.yolo_get_data, name='yolo_get_data'),
]
