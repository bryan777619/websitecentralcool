from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import CustomUser

class SignUpForm(UserCreationForm):
    nama = forms.CharField(
        max_length=100,
        required=True,
        help_text="Masukkan nama lengkap Anda.",
        widget=forms.TextInput(attrs={
            'placeholder': 'Masukkan nama lengkap Anda',
            'class': 'form-control'
        })
    )
    nomor_telepon = forms.CharField(
        max_length=15,
        required=True,
        help_text="Masukkan nomor telepon Anda.",
        widget=forms.TextInput(attrs={
            'placeholder': 'Masukkan nomor telepon Anda',
            'class': 'form-control'
        })
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Masukkan username Anda',
            'class': 'form-control'
        })
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Masukkan password Anda',
            'class': 'form-control'
        })
    )
    password2 = forms.CharField(
        label="Konfirmasi Password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Ulangi password Anda',
            'class': 'form-control'
        })
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'nama', 'nomor_telepon', 'password1', 'password2')

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Kata sandi tidak cocok.")
        if len(password1) < 8:
            raise ValidationError("Kata sandi harus minimal 8 karakter.")
        if not any(char.isdigit() for char in password1):
            raise ValidationError("Kata sandi harus mengandung setidaknya satu angka.")
        if not any(char.isupper() for char in password1):
            raise ValidationError("Kata sandi harus mengandung setidaknya satu huruf besar.")
        return password2

    def clean_nomor_telepon(self):
        nomor_telepon = self.cleaned_data.get('nomor_telepon')
        if not nomor_telepon.isdigit():
            raise ValidationError("Nomor telepon hanya boleh berisi angka.")
        if len(nomor_telepon) < 10 or len(nomor_telepon) > 15:
            raise ValidationError("Nomor telepon harus berisi antara 10 dan 15 digit.")
        return nomor_telepon

    def save(self, commit=True):
        user = super().save(commit=False)
        user.nama = self.cleaned_data['nama']
        user.nomor_telepon = self.cleaned_data['nomor_telepon']
        user.is_admin = False
        if commit:
            user.save()
        return user

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    remember_me = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput())

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError('Akun ini tidak aktif.', code='inactive')