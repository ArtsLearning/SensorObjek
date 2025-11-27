from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import RegisterForm

def register_view(request):
    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, "Akun berhasil dibuat! Silakan login.")
            return redirect('login')   # Jangan auto-login agar pesan muncul

        else:
            messages.error(request, "Pendaftaran gagal. Silakan cek kembali data Anda.")

    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login berhasil! Selamat datang.")
            return redirect('home')

        else:
            messages.error(request, "Username atau password salah!")

    return render(request, 'accounts/login.html')