from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import SignUpForm, CustomAuthenticationForm

def custom_login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Selamat datang kembali, {user.nama}!')
                if user.is_admin:
                    return redirect('admin_dashboard')
                else:
                    return redirect('home')
            else:
                messages.error(request, 'Username atau password tidak valid.')
        else:
            messages.error(request, 'Form tidak valid. Silakan coba lagi.')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Akun berhasil dibuat. Selamat datang, {user.nama}!')
            return redirect('home')
        else:
            messages.error(request, 'Terjadi kesalahan saat membuat akun. Silakan coba lagi.')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})