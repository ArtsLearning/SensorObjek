from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .forms import RegisterForm


# =========================
# REGISTER
# =========================
def register(request):
    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, "Akun berhasil dibuat! Silakan login.")
            return redirect('login')

        else:
            messages.error(request, "Pendaftaran gagal. Silakan cek kembali data Anda.")

    return render(request, 'accounts/register.html', {'form': form})


# =========================
# LOGIN
# =========================
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login berhasil! Selamat datang.")
            return redirect('dashboard')

        else:
            messages.error(request, "Username atau password salah!")

    return render(request, 'accounts/login.html')


# =========================
# CHANGE PASSWORD
# =========================
@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)

        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # agar tidak logout
            messages.success(request, "Password berhasil diubah.")
        else:
            for error in form.errors.values():
                messages.error(request, error)

        return redirect('setting')  # kembali ke halaman settings admin
