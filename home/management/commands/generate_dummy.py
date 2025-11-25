import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from home.models import Pelanggaran
import os

class Command(BaseCommand):
    help = 'Generate dummy data pelanggaran otomatis'

    def handle(self, *args, **kwargs):
        sample_image_path = os.path.join(
            settings.BASE_DIR, 
            "home/static/home/images/sample_pelanggar.jpg"
        )

        if not os.path.exists(sample_image_path):
            self.stdout.write(self.style.ERROR("Gambar sample tidak ditemukan!"))
            return

        lokasi_list = [
            "Jl. Ahmad Yani",
            "Jl. Sudirman",
            "Jl. Gajah Mada",
            "Jl. Diponegoro",
            "Jl. Imam Bonjol",
            "Jl. Veteran"
        ]

        for i in range(20):  # jumlah dummy data
            # Tanggal & waktu random
            tanggal_random = datetime.now().date() - timedelta(days=random.randint(1, 30))
            waktu_random = (datetime.now() - timedelta(minutes=random.randint(1, 1440))).time()

            pel = Pelanggaran(
                tanggal=tanggal_random,
                waktu=waktu_random,
                lokasi=random.choice(lokasi_list),
            )

            # Simpan objek dulu agar bisa upload file
            pel.save()

            # Upload gambar sample sebagai bukti foto
            with open(sample_image_path, "rb") as img_file:
                pel.bukti_foto.save(f"sample_{i}.jpg", File(img_file), save=True)

        self.stdout.write(self.style.SUCCESS("Berhasil generate 20 dummy data pelanggaran!"))
