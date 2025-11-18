from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .forms import RegisterForm

def register_view(request):
    form = RegisterForm()
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')  # Pastikan URL 'home' ada
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    msg = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('home')  # harus ada di urls.py
        else:
            msg = 'username / password salah'

    return render(request, 'accounts/login.html', {'msg': msg})


def logout_view(request):
    logout(request)
    return redirect('login')