from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import UserProfile


import os
import json
import time

from .models import (
    Pelanggaran,
    Notifikasi,
    TrafficHarian,
    SystemSetting
)

# ================================================================
# GLOBAL DATA UNTUK YOLO REALTIME (TIDAK DISIMPAN KE DB)
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
@login_required
def dashboard(request):
    pelanggaran_terbaru = Pelanggaran.objects.order_by('-id')[:5]
    notif_list = Notifikasi.objects.order_by('-created_at')[:5]
    notif_unread = Notifikasi.objects.filter(is_read=False).count()

    setting = SystemSetting.objects.first()

    return render(request, 'home/dashboard.html', {
        "pelanggaran_terbaru": pelanggaran_terbaru,
        "notif_list": notif_list,
        "notif_unread": notif_unread,
        "notif_enabled": setting.notif_enabled if setting else False
    })



# ================================================================
# MARK NOTIFIKASI SEBAGAI DIBACA
# ================================================================
def mark_read(request):
    Notifikasi.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})


# ================================================================
# LIVESTREAM ADMIN
# ================================================================
@login_required
def livestream_dashboard(request):
    return render(request, "home/livestream_dashboard.html")


# ================================================================
# SETTINGS ADMIN
# ================================================================
@login_required
def setting_page(request):
    setting, _ = SystemSetting.objects.get_or_create(id=1)

    if request.method == "POST":
        status = request.POST.get("notif_status")
        setting.notif_enabled = True if status == "1" else False
        setting.save()
        return redirect("setting")

    return render(request, 'home/settings_admin.html', {
        "setting": setting
    })



# ================================================================
# TABEL PELANGGARAN (ADMIN)
# ================================================================
@login_required
def tabel_pelanggaran(request):
    data = Pelanggaran.objects.all().order_by('-id')
    return render(request, 'home/tabel_pelanggaran.html', {'data': data})


# ================================================================
# DELETE DATA PELANGGARAN
# ================================================================
def delete_pelanggaran(request, id):
    pelanggaran = get_object_or_404(Pelanggaran, id=id)

    if pelanggaran.bukti_foto:
        try:
            if os.path.isfile(pelanggaran.bukti_foto.path):
                os.remove(pelanggaran.bukti_foto.path)
        except:
            pass

    pelanggaran.delete()
    return redirect('tabel_pelanggaran')


# ================================================================
# LOGOUT
# ================================================================
def logout_user(request):
    logout(request)
    return redirect('home')


# ================================================================
# EXPORT PDF PELANGGARAN
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
# API TERIMA DATA YOLO REALTIME (UNTUK DASHBOARD)
# ================================================================
@csrf_exempt
def yolo_test(request):
    global YOLO_DATA

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            YOLO_DATA["motor"] = int(data.get("motor", 0))
            YOLO_DATA["mobil"] = int(data.get("mobil", 0))
            YOLO_DATA["pelanggar"] = int(data.get("pelanggar", 0))
            YOLO_DATA["total"] = int(data.get("total", 0))
            YOLO_DATA["stream_active"] = bool(data.get("stream_active", True))
            YOLO_DATA["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

            return JsonResponse({"status": "ok"}, status=200)

        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)}, status=400)

    return JsonResponse({"status": "error", "msg": "POST only"}, status=405)


# ================================================================
# API KIRIM DATA YOLO REALTIME KE FRONTEND
# ================================================================
def get_yolo_data(request):
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

    return JsonResponse(YOLO_DATA)


# ================================================================
# API UPDATE TOTAL TRAFFIC HARIAN (INI YANG BARU)
# ================================================================
@csrf_exempt
def update_traffic_harian(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "msg": "POST only"}, status=405)

    data = json.loads(request.body.decode("utf-8"))
    today = date.today()

    traffic, created = TrafficHarian.objects.get_or_create(
        tanggal=today,
        defaults={
            "total_motor": 0,
            "total_mobil": 0,
            "total_pelanggar": 0,
        }
    )

    traffic.total_motor += int(data.get("motor", 0))
    traffic.total_mobil += int(data.get("mobil", 0))
    traffic.total_pelanggar += int(data.get("pelanggar", 0))
    traffic.save()

    return JsonResponse({
        "status": "ok",
        "tanggal": str(today),
        "motor": traffic.total_motor,
        "mobil": traffic.total_mobil,
        "pelanggar": traffic.total_pelanggar,
        "total": traffic.total_motor + traffic.total_mobil
    })


# ================================================================
# API GET TOTAL TRAFFIC HARIAN (UNTUK UI)
# ================================================================
def get_traffic_harian(request):
    today = date.today()
    traffic = TrafficHarian.objects.filter(tanggal=today).first()

    if not traffic:
        return JsonResponse({
            "motor": 0,
            "mobil": 0,
            "pelanggar": 0,
            "total": 0,
        })

    return JsonResponse({
        "motor": traffic.total_motor,
        "mobil": traffic.total_mobil,
        "pelanggar": traffic.total_pelanggar,
        "total": traffic.total_motor + traffic.total_mobil
    })


# ================================================================
# USER PELANGGARAN PAGE
# ================================================================
def user_pelanggaran(request):
    tanggal = request.GET.get("tanggal")
    data = Pelanggaran.objects.all().order_by('-id')

    if tanggal:
        data = data.filter(tanggal=tanggal)

    return render(request, "home/user_pelanggaran.html", {
        "data": data,
        "filter_tanggal": tanggal or "",
    })


# ================================================================
# API GET NOTIFIKASI REALTIME
# ================================================================
def get_notifications(request):
    setting = SystemSetting.objects.first()

    if not setting or not setting.notif_enabled:
        return JsonResponse({
            "unread_count": 0,
            "notifications": []
        })

    notif_list = Notifikasi.objects.order_by('-created_at')[:5]
    notif_unread = Notifikasi.objects.filter(is_read=False).count()

    data_list = []
    for n in notif_list:
        data_list.append({
            "pesan": n.pesan,
            "waktu": n.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return JsonResponse({
        "unread_count": notif_unread,
        "notifications": data_list
    })


# ================================================================
# API TREND TOTAL KENDARAAN PER BULAN (UNTUK GRAFIK DASHBOARD)
# ================================================================
def traffic_trend_bulanan(request):
    qs = (
        TrafficHarian.objects
        .annotate(bulan=TruncMonth("tanggal"))
        .values("bulan")
        .annotate(
            motor=Sum("total_motor"),
            mobil=Sum("total_mobil"),
        )
        .order_by("bulan")
    )

    labels = []
    totals = []

    for row in qs:
        labels.append(row["bulan"].strftime("%b %Y"))  # contoh: Jan 2025
        totals.append((row["motor"] or 0) + (row["mobil"] or 0))

    return JsonResponse({
        "labels": labels,
        "data": totals
    })


# ================================================================
# UPDATE PROFIL ADMIN (NAMA + FOTO)
# ================================================================
@login_required
def update_admin_profile(request):
    if request.method == "POST":
        user = request.user

        # AMAN: auto-create jika belum ada
        profile, created = UserProfile.objects.get_or_create(user=user)

        # UPDATE NAMA
        name = request.POST.get("admin_name")
        if not name:
            messages.error(request, "Nama admin tidak boleh kosong.")
            return redirect("setting")

        user.first_name = name

        # UPDATE FOTO
        if request.FILES.get("photo"):
            profile.photo = request.FILES["photo"]

        user.save()
        profile.save()

        messages.success(
            request,
            "Profil admin berhasil diperbarui."
        )
        return redirect("setting")


