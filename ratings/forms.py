from django import forms
from .models import Rating

class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['rating', 'review']
        labels = {
            'rating': 'Rating',
            'review': 'Ulasan'
        }
        widgets = {
            'rating': forms.RadioSelect(attrs={
                'class': 'rating-input'
            }),
            'review': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tulis ulasan Anda di sini...'
            })
        }