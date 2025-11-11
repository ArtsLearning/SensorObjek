from django.shortcuts import render

def home(request):
    """View untuk halaman home"""
    context = {
        'page_title': 'Home',
    }
    return render(request, 'home/index.html', context)

def livestream(request):
    """View untuk halaman livestream"""
    context = {
        'page_title': 'Livestream',
    }
    return render(request, 'home/livestream.html', context)