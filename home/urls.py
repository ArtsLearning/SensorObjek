from django.urls import path
from . import views
from .API_data_pelanggar import save_violation
from home.views import mark_read

urlpatterns = [
    # =============================
    # HALAMAN UTAMA & DASAR
    # =============================
    path('', views.home, name='home'),
    path('livestream/', views.livestream, name='livestream'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('livestream-dashboard/', views.livestream_dashboard, name='livestream_dashboard'),
    path('user-pelanggaran/', views.user_pelanggaran, name='user_pelanggaran'),
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

    path("api/update-traffic-harian/", views.update_traffic_harian),
    path("api/traffic-trend-bulanan/", views.traffic_trend_bulanan),



    # versi lama (dipertahankan untuk kompatibilitas)
    path('api/yolo-test/', views.yolo_test, name='yolo_test'),

    # endpoint pengiriman data terbaru ke dashboard frontend
    path('api/yolo-data/', views.get_yolo_data, name='get_yolo_data'),

    # API_data_pelanggar
    path("api/save-violation/", save_violation, name="save_violation"),


    # versi baru (placeholder untuk pengembangan selanjutnya)
    # pastikan belum diaktifkan karena views.yolo_get_data belum dibuat
    # path('api/yolo-receive/', views.yolo_receive_data, name='yolo_receive_data'),
    # path('api/yolo-get/', views.yolo_get_data, name='yolo_get_data'),
    
    path("notif/read-all/", mark_read, name="notif_read_all"),
    # API NOTIFIKASI REALTIME
    path('api/get-notif/', views.get_notifications, name='get_notifications'),
]