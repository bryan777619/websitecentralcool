from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import RegexValidator

class CustomUserManager(BaseUserManager):
    def create_user(self, username, nama, nomor_telepon, password=None, is_admin=False):
        if not username:
            raise ValueError('Users must have a username')
        user = self.model(
            username=username,
            nama=nama,
            nomor_telepon=nomor_telepon,
            is_admin=is_admin
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, nama, nomor_telepon, password):
        user = self.create_user(
            username=username,
            nama=nama,
            nomor_telepon=nomor_telepon,
            password=password,
            is_admin=True
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=50, unique=True)
    nama = models.CharField(max_length=100)
    nomor_telepon = models.CharField(max_length=15, validators=[RegexValidator(
        regex=r'^\+?1?\d{9,15}$', message="Nomor telepon harus dalam format yang benar."
    )])
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['nama', 'nomor_telepon']

    class Meta:
        db_table = 'pengguna'

    def __str__(self):
        return self.username

    def update_last_login(self):
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])