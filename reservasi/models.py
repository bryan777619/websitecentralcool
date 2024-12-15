from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField

class Reservasi(models.Model):
    STATUS_CHOICES = (
        ('Dalam Perbaikan', 'Dalam Perbaikan'),
        ('Selesai', 'Selesai'),
        ('Dibatalkan', 'Dibatalkan'),
    )
    
    LAYANAN_CHOICES = (
        ('Servis AC', 'Servis AC'),
        ('Isi Freon', 'Isi Freon'),
        ('Pembersihan', 'Pembersihan'),
        ('Perbaikan Komponen', 'Perbaikan Komponen'),
    )

    nominal_pembayaran = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    MAX_RESERVATIONS_PER_SLOT = 3  

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reservasi')
    tanggal = models.DateField()
    waktu = models.TimeField()
    layanan = models.CharField(
        max_length=100,
        choices=LAYANAN_CHOICES,
        default='Servis AC'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Dalam Perbaikan')
    status_updated_at = models.DateTimeField(null=True, blank=True)  # New field for status update tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_cancelled = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    recommended_service = models.CharField(max_length=100, blank=True, null=True)

    def clean(self):
        super().clean()

        if self.waktu:
            if self.waktu < timezone.datetime.strptime('09:00', '%H:%M').time() or \
            self.waktu > timezone.datetime.strptime('16:00', '%H:%M').time():
                raise ValidationError('Reservasi hanya dapat dilakukan antara jam 09:00 hingga 16:00.')

        if self.tanggal:
            if self.tanggal.weekday() == 6: 
                raise ValidationError(
                    'Mohon maaf, bengkel tutup di hari Minggu. Silakan pilih hari Senin sampai Sabtu untuk reservasi.'
                )

    def get_formatted_payment(self):
        """Return formatted payment amount"""
        if self.nominal_pembayaran:
            return f"Rp {int(self.nominal_pembayaran):,}".replace(',', '.')
        return None

    def save(self, *args, **kwargs):
        if not self.pk:
            # New object being created
            self.status_updated_at = timezone.now()
        else:
            # Existing object being updated
            old_obj = Reservasi.objects.filter(pk=self.pk).first()
            if old_obj and old_obj.status != self.status:
                # Status has changed, update the timestamp
                self.status_updated_at = timezone.now()
                
                # Handle status-specific actions
                if self.status == 'Dibatalkan':
                    self.is_cancelled = True
                elif self.status == 'Selesai':
                    self.completed_at = timezone.now()

        if self.nominal_pembayaran:
            self.nominal_pembayaran = round(float(self.nominal_pembayaran), 2)
            
        self.full_clean()
        super().save(*args, **kwargs)

    def cancel(self):
        """Cancel the reservation"""
        self.status = 'Dibatalkan'
        self.is_cancelled = True
        self.save(update_fields=['status', 'is_cancelled', 'updated_at', 'status_updated_at'])
        return True

    def mark_as_complete(self):
        """Mark reservation as complete"""
        self.status = 'Selesai'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at', 'status_updated_at'])
    
        recommendation_usage = RecommendationUsage.objects.filter(
            user=self.user,
            current_reservation=self
        ).first()
    
        if recommendation_usage:
            recommendation_usage.reset_usage()

    def __str__(self):
        return f"{self.user.username} - {self.tanggal} {self.waktu}"

    class Meta:
        ordering = ['-tanggal', '-waktu']
        verbose_name = 'Reservasi'
        verbose_name_plural = 'Reservasi'

# Rest of the models remain unchanged
class CarType(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Tipe Mobil'
        verbose_name_plural = 'Tipe Mobil'

class CarBrand(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Merek Mobil'
        verbose_name_plural = 'Merek Mobil'

class ACProblem(models.Model):
    description = models.CharField(max_length=100)

    def __str__(self):
        return self.description

    class Meta:
        verbose_name = 'Masalah AC'
        verbose_name_plural = 'Masalah AC'

class Recommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    car_type = models.ForeignKey(CarType, on_delete=models.CASCADE)
    car_brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE)
    problems = models.ManyToManyField(ACProblem)
    recommended_services = models.JSONField(default=list)
    service_descriptions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    ml_model_used = models.CharField(max_length=50, null=True)
    confidence_scores = models.JSONField(default=list)

    def __str__(self):
        return f"{self.user.username} - {self.car_brand} {self.car_type}"

    class Meta:
        verbose_name = 'Rekomendasi'
        verbose_name_plural = 'Rekomendasi'

User = get_user_model()

class RecommendationUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    used_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True)
    current_reservation = models.ForeignKey(
        'Reservasi', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommendation_usage'
    )

    def reset_usage(self):
        """Reset usage count"""
        self.used_count = 0
        self.last_used = None
        self.save()

    class Meta:
        verbose_name = 'Penggunaan Rekomendasi'
        verbose_name_plural = 'Penggunaan Rekomendasi'
        unique_together = ('user', 'current_reservation')

class PredictionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    car_type = models.CharField(max_length=100)
    car_brand = models.CharField(max_length=100)
    problems = ArrayField(models.CharField(max_length=255))
    predicted_services = ArrayField(models.CharField(max_length=255))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']