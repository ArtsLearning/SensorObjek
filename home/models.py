from django.db import models


# =====================================================
# MODEL PELANGGARAN
# =====================================================
class Pelanggaran(models.Model):
    bukti_foto = models.ImageField(upload_to='pelanggar/', null=True, blank=True)
    tanggal = models.DateField(auto_now_add=True)
    waktu = models.TimeField(auto_now_add=True)
    lokasi = models.CharField(max_length=255, default="Gerbang Masuk Polibatam")
    jenis = models.CharField(max_length=100, default="Tidak Pakai Helm")

    def __str__(self):
        return f"Pelanggaran #{self.id} - {self.jenis} ({self.tanggal})"


# =====================================================
# MODEL NOTIFIKASI
# =====================================================
class Notifikasi(models.Model):
    pesan = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.pesan


# =====================================================
# MODEL TRAFFIC HARIAN
# =====================================================
class TrafficHarian(models.Model):
    tanggal = models.DateField(unique=True)

    total_motor = models.PositiveIntegerField(default=0)
    total_mobil = models.PositiveIntegerField(default=0)
    total_pelanggar = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Traffic {self.tanggal}"
