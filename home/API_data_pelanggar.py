from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.files.base import ContentFile
from .models import Pelanggaran
import base64
import datetime

@api_view(['POST'])
def save_violation(request):
    try:
        image_base64 = request.data.get("image")
        lokasi = request.data.get("lokasi", "Tidak diketahui")

        if not image_base64:
            return Response({"status": "error", "msg": "No image"}, status=400)

        # Decode base64
        format, imgstr = image_base64.split(';base64,')
        ext = format.split('/')[-1]

        filename = f"pelanggar_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        file_data = ContentFile(base64.b64decode(imgstr), name=filename)

        Pelanggaran.objects.create(
            bukti_foto=file_data,
            lokasi=lokasi,
        )

        return Response({"status": "ok", "msg": "Pelanggaran disimpan"})

    except Exception as e:
        return Response({"status": "error", "msg": str(e)}, status=500)
