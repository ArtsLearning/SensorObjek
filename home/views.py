from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth import logout

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

import os

from .models import Pelanggaran


# ===============================
# HOME PAGE
# ===============================
def home(request):
    return render(request, 'home/index.html', {'page_title': 'Home'})


# ===============================
# LIVESTREAM PAGE
# ===============================
def livestream(request):
    return render(request, 'home/livestream.html')


# ===============================
# DASHBOARD PAGE
# ===============================
def dashboard(request):
    return render(request, 'home/dashboard.html')


# ===============================
# TABEL PELANGGARAN
# ===============================
def tabel_pelanggaran(request):
    data = Pelanggaran.objects.all().order_by('-id')   # data terbaru di atas
    return render(request, 'home/tabel_pelanggaran.html', {'data': data})


# ===============================
# DELETE PELANGGARAN
# ===============================
def delete_pelanggaran(request, id):
    pelanggaran = get_object_or_404(Pelanggaran, id=id)

    # Hapus gambar dari sistem
    if pelanggaran.bukti_foto:
        if os.path.isfile(pelanggaran.bukti_foto.path):
            os.remove(pelanggaran.bukti_foto.path)

    # Hapus data dari database
    pelanggaran.delete()

    return redirect('tabel_pelanggaran')



def logout_user(request):
    logout(request)
    return redirect('home')



# ===============================
# EXPORT PDF
# ===============================
def export_pdf(request, id):
    pelanggaran = get_object_or_404(Pelanggaran, id=id)

    # Nama file PDF
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename=pelanggaran_{id}.pdf'

    # Setup PDF
    pdf = canvas.Canvas(response, pagesize=A4)

    # Judul
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 800, "Laporan Pelanggaran Kendaraan")

    # Data Pelanggaran
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"ID Pelanggaran : {pelanggaran.id}")
    pdf.drawString(50, 750, f"Tanggal        : {pelanggaran.tanggal}")
    pdf.drawString(50, 730, f"Waktu          : {pelanggaran.waktu}")
    pdf.drawString(50, 710, f"Lokasi         : {pelanggaran.lokasi}")

    # Masukkan gambar bukti
    if pelanggaran.bukti_foto:
        image_path = os.path.join(settings.MEDIA_ROOT, str(pelanggaran.bukti_foto))

        try:
            pdf.drawImage(image_path, 50, 450, width=300, height=250)
        except:
            pdf.drawString(50, 450, "(Gambar tidak dapat dimuat)")

    pdf.showPage()
    pdf.save()

    return response



