from django.shortcuts import render

def home(request):
    """View untuk halaman home"""
    context = {
        'page_title': 'Home',
    }
    return render(request, 'home/index.html', context)

def about(request):
    """View untuk halaman about"""
    context = {
        'page_title': 'About Me',
    }
    return render(request, 'home/about.html', context)

def gallery(request):
    """View untuk halaman galeri"""
    context = {
        'page_title': 'Galeri',
    }
    return render(request, 'home/gallery.html', context)