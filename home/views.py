from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

import os
import json
import time

from .models import Pelanggaran


# ================================================================
# GLOBAL DATA UNTUK YOLO REALTIME
# ================================================================
YOLO_DATA = {
    "motor": 0,
    "mobil": 0,
    "pelanggar": 0,
    "total": 0,
    "stream_active": False,
    "last_update": None,
}


# ================================================================
# HOME PAGE
# ================================================================
def home(request):
    return render(request, 'home/index.html', {'page_title': 'Home'})


# ================================================================
# LIVESTREAM PAGE (USER)
# ================================================================
def livestream(request):
    return render(request, 'home/livestream.html')


# ================================================================
# DASHBOARD ADMIN
# ================================================================
def dashboard(request):
    return render(request, 'home/dashboard.html')


# ================================================================
# LIVESTREAM DI DALAM DASHBOARD ADMIN
# ================================================================
def livestream_dashboard(request):
    return render(request, "home/livestream_dashboard.html")


# ================================================================
# SETTINGS ADMIN
# ================================================================
def setting_page(request):
    return render(request, 'home/settings_admin.html')


# ================================================================
# TABEL PELANGGARAN
# ================================================================
def tabel_pelanggaran(request):
    data = Pelanggaran.objects.all().order_by('-id')  # data terbaru di atas
    return render(request, 'home/tabel_pelanggaran.html', {'data': data})


# ================================================================
# DELETE PELANGGARAN
# ================================================================
def delete_pelanggaran(request, id):
    pelanggaran = get_object_or_404(Pelanggaran, id=id)

    # Hapus foto bukti
    if pelanggaran.bukti_foto:
        if os.path.isfile(pelanggaran.bukti_foto.path):
            os.remove(pelanggaran.bukti_foto.path)

    # Hapus data DB
    pelanggaran.delete()

    return redirect('tabel_pelanggaran')


# ================================================================
# LOGOUT
# ================================================================
def logout_user(request):
    logout(request)
    return redirect('home')


# ================================================================
# EXPORT PDF LAPORAN PELANGGARAN
# ================================================================
def export_pdf(request, id):
    pelanggaran = get_object_or_404(Pelanggaran, id=id)

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename=pelanggaran_{id}.pdf'

    pdf = canvas.Canvas(response, pagesize=A4)

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 800, "Laporan Pelanggaran Kendaraan")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"ID Pelanggaran : {pelanggaran.id}")
    pdf.drawString(50, 750, f"Tanggal        : {pelanggaran.tanggal}")
    pdf.drawString(50, 730, f"Waktu          : {pelanggaran.waktu}")
    pdf.drawString(50, 710, f"Lokasi         : {pelanggaran.lokasi}")

    if pelanggaran.bukti_foto:
        image_path = os.path.join(settings.MEDIA_ROOT, str(pelanggaran.bukti_foto))
        try:
            pdf.drawImage(image_path, 50, 450, width=300, height=250)
        except:
            pdf.drawString(50, 450, "(Gambar tidak dapat dimuat)")

    pdf.showPage()
    pdf.save()

    return response


# ================================================================
# ENDPOINT UNTUK YOLO — MENERIMA DATA (POST)
# ================================================================
@csrf_exempt
def yolo_test(request):
    """
    Endpoint untuk menerima data dari YOLO.
    Format JSON:
    {
        "motor": 5,
        "mobil": 3,
        "pelanggar": 1,
        "total": 9,
        "stream_active": true
    }
    """
    global YOLO_DATA

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            # Validasi input
            YOLO_DATA["motor"] = int(data.get("motor", 0))
            YOLO_DATA["mobil"] = int(data.get("mobil", 0))
            YOLO_DATA["pelanggar"] = int(data.get("pelanggar", 0))
            YOLO_DATA["total"] = int(data.get("total", 0))
            YOLO_DATA["stream_active"] = bool(data.get("stream_active", True))
            YOLO_DATA["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Debug ke console
            print("\n=== DATA DARI YOLO ===")
            print(json.dumps(YOLO_DATA, indent=4))

            return JsonResponse({"status": "ok", "msg": "Data YOLO diterima"}, status=200)

        except Exception as e:
            print("Error saat parsing data YOLO:", e)
            return JsonResponse({"status": "error", "msg": "Invalid JSON"}, status=400)

    return JsonResponse({"status": "error", "msg": "Gunakan metode POST"}, status=405)


# ================================================================
# ENDPOINT UNTUK DASHBOARD — MENGIRIM DATA TERBARU (GET)
# ================================================================
def get_yolo_data(request):
    """
    Dipanggil oleh dashboard/livestream setiap 1 detik.
    Mengirim data terbaru yang diterima dari YOLO.
    """
    global YOLO_DATA

    if YOLO_DATA["last_update"] is None:
        return JsonResponse({
            "motor": 0,
            "mobil": 0,
            "pelanggar": 0,
            "total": 0,
            "stream_active": False,
            "last_update": None
        })

    return JsonResponse(YOLO_DATA, safe=False)
