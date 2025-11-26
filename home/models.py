from django.db import models

class Pelanggaran(models.Model):
    bukti_foto = models.ImageField(upload_to='pelanggar/', null=True, blank=True)
    tanggal = models.DateField(auto_now_add=True)  # otomatis ambil tanggal sekarang
    waktu = models.TimeField(auto_now_add=True)    # otomatis ambil waktu sekarang
    lokasi = models.CharField(max_length=255, default="-")
    jenis = models.CharField(max_length=100, default="Tidak Pakai Helm")  # jenis pelanggaran

    def __str__(self):
        return f"Pelanggaran {self.id} - {self.jenis}"
