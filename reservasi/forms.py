from django import forms
from .models import Reservasi, CarType, CarBrand, ACProblem, Recommendation
from datetime import datetime, date, time
from django.utils import timezone
from django import forms
from .models import Reservasi, CarType, CarBrand, ACProblem, Recommendation
from datetime import datetime, date, time
from django.utils import timezone
from django.core.exceptions import ValidationError

class ReservasiForm(forms.ModelForm):
    class Meta:
        model = Reservasi
        fields = ['tanggal', 'waktu', 'layanan']
        widgets = {
            'tanggal': forms.DateInput(
                attrs={
                    'type': 'date', 
                    'min': date.today().isoformat(),
                    'class': 'form-control'
                }
            ),
            'waktu': forms.TimeInput(
                attrs={
                    'type': 'time', 
                    'min': '09:00', 
                    'max': '16:00',
                    'class': 'form-control'
                }
            ),
            'layanan': forms.Select(
                attrs={
                    'class': 'form-control'
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        tanggal = cleaned_data.get('tanggal')
        waktu = cleaned_data.get('waktu')
        
        if tanggal and waktu:
            # Validasi hari kerja (Senin-Sabtu)
            if tanggal.weekday() == 6:
                raise ValidationError(
                    "Mohon maaf, bengkel tutup di hari Minggu. Silakan pilih hari Senin sampai Sabtu untuk reservasi."
                )

            # Validasi tanggal dan waktu di masa depan
            reservasi_datetime = datetime.combine(tanggal, waktu)
            if reservasi_datetime < datetime.now():
                raise ValidationError("Tanggal dan waktu reservasi harus di masa depan.")

            # Validasi jam kerja
            if waktu < time(9, 0) or waktu > time(16, 0):
                raise ValidationError("Reservasi hanya dapat dilakukan antara jam 09:00 hingga 16:00.")

            # Validasi slot reservasi yang tersisa
            existing_reservations = Reservasi.objects.filter(
                tanggal=tanggal,
                waktu=waktu,
                is_cancelled=False
            ).count()

            if existing_reservations >= Reservasi.MAX_RESERVATIONS_PER_SLOT:
                formatted_time = waktu.strftime("%H:%M")
                formatted_date = tanggal.strftime("%d-%m-%Y")
                # Change the validation error to be associated with 'waktu' instead of 'tanggal'
                raise ValidationError({
                    'waktu': f"Mohon maaf, slot reservasi untuk pukul {formatted_time} pada tanggal {formatted_date} sudah penuh. Silakan pilih waktu reservasi lainnya."
                })

        return cleaned_data

class RecommendationForm(forms.ModelForm):
    problems = forms.ModelMultipleChoiceField(
        queryset=ACProblem.objects.all(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '3',  # Show 3 visible options
        }),
        label='Masalah yang Dialami (maksimal 3)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['car_type'].queryset = CarType.objects.all()
        self.fields['car_brand'].queryset = CarBrand.objects.all()
        
        self.fields['car_type'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Pilih jenis mobil'
        })
        self.fields['car_brand'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Pilih merek mobil'
        })

    def clean_problems(self):
        problems = self.cleaned_data.get('problems')
        if problems and len(problems) > 3:
            raise ValidationError('Maksimal 3 masalah yang dapat dipilih.')
        return problems

    class Meta:
        model = Recommendation
        fields = ['car_type', 'car_brand', 'problems']
        labels = {
            'car_type': 'Jenis Mobil',
            'car_brand': 'Merek Mobil',
        }