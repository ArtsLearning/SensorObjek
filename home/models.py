from django.db import models

class Pelanggaran(models.Model):
    bukti_foto = models.ImageField(upload_to='pelanggar/', null=True, blank=True)
    tanggal = models.DateField(auto_now_add=True)  # otomatis ambil tanggal sekarang
    waktu = models.TimeField(auto_now_add=True)    # otomatis ambil waktu sekarang
    lokasi = models.CharField(max_length=255, default="-")
    jenis = models.CharField(max_length=100, default="Tidak Pakai Helm")  # jenis pelanggaran

    def _str_(self):
        return f"Pelanggaran {self.id} - {self.jenis}"

class Notifikasi(models.Model):
    pesan = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def _str_(self):
        return self.pesan