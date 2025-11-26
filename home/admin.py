from django.contrib import admin
from .models import Pelanggaran


# ===============================
# PENDAFTARAN MODEL KE DJANGO ADMIN
# ===============================
@admin.register(Pelanggaran)
class PelanggaranAdmin(admin.ModelAdmin):
    """
    Kelas ini mengatur bagaimana model Pelanggaran
    ditampilkan, difilter, dan dicari di halaman admin Django.
    """

    # Kolom yang akan muncul di daftar tabel admin
    list_display = ("id", "tanggal", "waktu", "lokasi", "bukti_foto")

    # Tambahkan fitur filter di sidebar admin
    list_filter = ("tanggal",)

    # Tambahkan kolom pencarian di atas tabel
    search_fields = ("lokasi",)

    # Urutan data (opsional)
    ordering = ("-tanggal", "-waktu")

    # Jumlah item per halaman (opsional)
    list_per_page = 20

    # Judul halaman admin (opsional, lebih rapi)
    verbose_name = "Data Pelanggaran"
    verbose_name_plural = "Data Pelanggaran"


# ===============================
# CATATAN:
# Jangan daftarkan ulang model Pelanggaran secara manual
# karena sudah dilakukan otomatis lewat @admin.register
# ===============================
