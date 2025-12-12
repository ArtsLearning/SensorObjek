from django.contrib import admin
from .models import Pelanggaran, Notifikasi, TrafficHarian


# =====================================================
# ADMIN PELANGGARAN
# =====================================================
@admin.register(Pelanggaran)
class PelanggaranAdmin(admin.ModelAdmin):
    list_display = ("id", "tanggal", "waktu", "lokasi", "jenis")
    list_filter = ("tanggal", "lokasi")
    search_fields = ("lokasi", "jenis")
    ordering = ("-tanggal", "-waktu")
    list_per_page = 20


# =====================================================
# ADMIN NOTIFIKASI
# =====================================================
@admin.register(Notifikasi)
class NotifikasiAdmin(admin.ModelAdmin):
    list_display = ("pesan", "created_at", "is_read")
    list_filter = ("is_read",)
    ordering = ("-created_at",)


# =====================================================
# ADMIN TRAFFIC HARIAN (INI YANG ERROR TADI)
# =====================================================
@admin.register(TrafficHarian)
class TrafficHarianAdmin(admin.ModelAdmin):
    list_display = (
        "tanggal",
        "total_motor",
        "total_mobil",
        "total_pelanggar",
    )

    list_filter = ("tanggal",)
    ordering = ("-tanggal",)
