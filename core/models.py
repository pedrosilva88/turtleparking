from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db.models import Count, Q
from datetime import timedelta
from django.contrib.admin.filters import SimpleListFilter

class ProfileManager(BaseUserManager):
    def create_user(self, username, email, name, password=None, role='customer', **extra_fields):
        if not email:
            raise ValueError('Email is required')
        if not username:
            raise ValueError('Username is required')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, name=name, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, name, password, role='business', **extra_fields)

class Profile(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('employee', 'Employee'),
        ('business', 'Manager'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'name']

    objects = ProfileManager()

class Employee(models.Model):
    user = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='employee_profile')
    ROLE_TYPE_CHOICES = (
        ('valet', 'Valet'),
        ('shuttle', 'Shuttle Driver'),
    )
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES)

class Vehicle(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='vehicles')
    plate = models.CharField(max_length=20)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)

class ParkingSpot(models.Model):
    identifier = models.CharField(max_length=20, unique=True)
    code = models.CharField(max_length=10, unique=True, null=True, blank=True)  # Ex: A-1, B-5
    is_active = models.BooleanField(default=True)

class PriceTable(models.Model):
    base_price_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=8.0)
    valet_price_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=5.0)
    car_wash_price = models.DecimalField(max_digits=6, decimal_places=2, default=20.0)
    keep_key_price_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=2.0)
    max_price_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=60.0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Price Table ({self.last_updated:%Y-%m-%d %H:%M})"

class Reservation(models.Model):
    SERVICE_CHOICES = (
        ('standard', 'Standard'),
        ('valet', 'Valet'),
        ('shuttle', 'Shuttle'),
    )
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reservations', null=True, blank=True)
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE)
    parking_spot = models.ForeignKey('ParkingSpot', on_delete=models.SET_NULL, null=True, blank=True)
    employee = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True)
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=20, default='active')
    total_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    valet_entrega = models.BooleanField(default=False)
    valet_recolha = models.BooleanField(default=False)
    shuttle_entrega = models.BooleanField(default=False)
    shuttle_recolha = models.BooleanField(default=False)
    car_wash = models.BooleanField(default=False)
    keep_key = models.BooleanField(default=False)
    calculated_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)


# Daily price history per reservation
class ReservationDay(models.Model):  # Daily price history per reservation
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    price = models.IntegerField(help_text="Base price agreed for this day, rounded down.")
    valet_delivery_price = models.IntegerField(default=0, help_text="Valet delivery price for this day.")
    valet_pickup_price = models.IntegerField(default=0, help_text="Valet pickup price for this day.")
    shuttle_delivery_price = models.IntegerField(default=0, help_text="Shuttle delivery price for this day.")
    shuttle_pickup_price = models.IntegerField(default=0, help_text="Shuttle pickup price for this day.")
    car_wash_price = models.IntegerField(default=0, help_text="Car wash price for this day (only the day before pickup if applicable).")
    keep_key_price = models.IntegerField(default=0, help_text="Keep key price for this day.")
    class Meta:
        unique_together = ("reservation", "date")
        ordering = ["date"]
    def __str__(self):
        return f"{self.reservation.id} - {self.date}: {self.price}€ (+extras)"

# Utility function for dynamic price calculation

def calculate_reservation_price(start_datetime, end_datetime, valet=False, car_wash=False, keep_key=False):
    from .models import ParkingSpot, Reservation, PriceTable
    import math
    # Get price table (assume only one)
    price_table = PriceTable.objects.first()
    if not price_table:
        # Defaults if not exists
        base = 8.0
        max_price = 60.0
        valet_price = 5.0
        car_wash_price = 20.0
        keep_key_price = 2.0
    else:
        base = float(price_table.base_price_per_day)
        max_price = float(price_table.max_price_per_day)
        valet_price = float(price_table.valet_price_per_day)
        car_wash_price = float(price_table.car_wash_price)
        keep_key_price = float(price_table.keep_key_price_per_day)

    # Calculate number of days (minimum 1)
    days = (end_datetime.date() - start_datetime.date()).days
    if days < 1:
        days = 1

    total_spots = ParkingSpot.objects.filter(is_active=True).count()
    total = 0.0
    for i in range(days):
        day = start_datetime.date() + timedelta(days=i)
        occupied = Reservation.objects.filter(
            start_datetime__date__lte=day,
            end_datetime__date__gte=day,
            status='active',
            parking_spot__isnull=False
        ).count()
        occupancy = occupied / total_spots if total_spots else 0
        if occupancy <= 0.6:
            day_price = base
        else:
            # Linear up to max_price
            day_price = base + (max_price - base) * ((occupancy - 0.6) / 0.4)
            day_price = min(day_price, max_price)
        total += day_price
    # Extras
    if valet:
        total += valet_price * days
    if car_wash:
        total += car_wash_price
    if keep_key:
        total += keep_key_price * days
    return round(total, 2)

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
