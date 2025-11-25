from django.db import models

class Pelanggaran(models.Model):
    bukti_foto = models.ImageField(upload_to='pelanggar/')
    tanggal = models.DateField()
    waktu = models.TimeField()
    lokasi = models.CharField(max_length=255, default="-")

    def __str__(self):
        return f"Pelanggaran {self.id}"
