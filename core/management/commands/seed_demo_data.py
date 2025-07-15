from django.core.management.base import BaseCommand
from core.models import Profile, Vehicle, ParkingSpot, Reservation, ReservationDay, calculate_reservation_price
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import datetime, timedelta
import random
from collections import defaultdict

class Command(BaseCommand):
    help = 'Populate the database with demo customers, spots, and reservations.'

    def handle(self, *args, **options):
        # Create 100 parking spots
        spots = []
        for i in range(1, 101):
            code = f"{chr(65 + (i-1)//10)}-{(i-1)%10+1}"
            spot, _ = ParkingSpot.objects.get_or_create(identifier=f"spot-{i}", defaults={"code": code, "is_active": True})
            spots.append(spot)
        self.stdout.write(self.style.SUCCESS('Created 100 parking spots.'))

        # Create 100 customers
        users = []
        for i in range(1, 101):
            username = f"customer{i}"
            email = f"customer{i}@demo.com"
            user, created = Profile.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "name": f"Customer {i}",
                    "role": "customer",
                    "password": make_password("password123")
                }
            )
            users.append(user)
        self.stdout.write(self.style.SUCCESS('Created 100 customers.'))

        # Create 1 vehicle per customer
        vehicles = []
        for i, user in enumerate(users, 1):
            plate = f"AA-{i:02d}-ZZ"
            v, _ = Vehicle.objects.get_or_create(user=user, plate=plate, defaults={"model": "DemoCar", "color": "Blue"})
            vehicles.append(v)
        self.stdout.write(self.style.SUCCESS('Created 100 vehicles.'))

        # Remove all existing reservations
        Reservation.objects.all().delete()
        self.stdout.write(self.style.WARNING('All reservations removed.'))

        # Preload existing occupation (should be empty, but for robustness)
        spot_calendar = defaultdict(set)  # {date: set(spot_id)}
        # Create 25 reservations of 5 days for each customer, random dates between August and November, only if there is availability
        start_date = datetime(timezone.now().year, 8, 1)
        end_date = datetime(timezone.now().year, 11, 25)  # Last possible start for 5 days in November
        for i, user in enumerate(users):
            vehicle = vehicles[i]
            created_count = 0
            attempts = 0
            while created_count < 25 and attempts < 1000:
                rand_days = random.randint(0, (end_date - start_date).days)
                naive_res_start = start_date + timedelta(days=rand_days)
                naive_res_end = naive_res_start + timedelta(days=5)
                res_start = timezone.make_aware(naive_res_start, timezone.get_default_timezone())
                res_end = timezone.make_aware(naive_res_end, timezone.get_default_timezone())
                days = (res_end.date() - res_start.date()).days
                if days < 1:
                    days = 1
                # Find an available spot for all days of the period using in-memory calendar
                available_spot = None
                for spot in spots:
                    spot_id = spot.id
                    conflict = False
                    for i_day in range(days):
                        day = res_start.date() + timedelta(days=i_day)
                        if spot_id in spot_calendar[day]:
                            conflict = True
                            break
                    if not conflict:
                        available_spot = spot
                        break
                if not available_spot:
                    attempts += 1
                    continue
                # Calculate daily prices
                import math
                daily_prices = []
                for i_day in range(days):
                    day = res_start.date() + timedelta(days=i_day)
                    price = calculate_reservation_price(
                        res_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i_day),
                        res_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i_day+1),
                        False, False, False
                    )
                    price = math.floor(price)
                    daily_prices.append((day, price))
                # Random extras for demo
                valet_delivery = random.choice([True, False])
                valet_pickup = random.choice([True, False])
                shuttle_delivery = random.choice([True, False])
                shuttle_pickup = random.choice([True, False])
                car_wash = random.choice([True, False])
                keep_key = random.choice([True, False])
                # Get current prices for extras
                from core.models import PriceTable
                price_table = PriceTable.objects.first()
                valet_price = int(price_table.valet_price_per_day) if price_table else 5
                shuttle_price = 0  # Set if price exists
                car_wash_price = int(price_table.car_wash_price) if price_table else 20
                keep_key_price = int(price_table.keep_key_price_per_day) if price_table else 2
                total = 0
                reservation_days = []
                for i_day, (day, base_price) in enumerate(daily_prices):
                    is_first = (i_day == 0)
                    is_last = (i_day == days - 1)
                    is_day_before_last = (i_day == days - 2)
                    day_valet_delivery = valet_delivery and is_first
                    day_valet_pickup = valet_pickup and is_last
                    day_shuttle_delivery = shuttle_delivery and is_first
                    day_shuttle_pickup = shuttle_pickup and is_last
                    day_car_wash = car_wash and is_day_before_last
                    day_keep_key = keep_key
                    v_delivery = valet_price if day_valet_delivery else 0
                    v_pickup = valet_price if day_valet_pickup else 0
                    s_delivery = shuttle_price if day_shuttle_delivery else 0
                    s_pickup = shuttle_price if day_shuttle_pickup else 0
                    c_wash = car_wash_price if day_car_wash else 0
                    k_key = keep_key_price if day_keep_key else 0
                    day_total = base_price + v_delivery + v_pickup + s_delivery + s_pickup + c_wash + k_key
                    total += day_total
                    reservation_days.append({
                        'date': day,
                        'price': base_price,
                        'valet_delivery_price': v_delivery,
                        'valet_pickup_price': v_pickup,
                        'shuttle_delivery_price': s_delivery,
                        'shuttle_pickup_price': s_pickup,
                        'car_wash_price': c_wash,
                        'keep_key_price': k_key,
                    })
                reservation = Reservation.objects.create(
                    user=user,
                    vehicle=vehicle,
                    parking_spot=available_spot,
                    service_type="standard",
                    start_datetime=res_start,
                    end_datetime=res_end,
                    status="active",
                    calculated_price=total,
                    total_price=total,
                    valet_entrega=valet_delivery,
                    valet_recolha=valet_pickup,
                    shuttle_entrega=shuttle_delivery,
                    shuttle_recolha=shuttle_pickup,
                    car_wash=car_wash,
                    keep_key=keep_key,
                )
                # Bulk create ReservationDay
                days_objs = [
                    ReservationDay(
                        reservation=reservation,
                        date=day['date'],
                        price=day['price'],
                        valet_delivery_price=day['valet_delivery_price'],
                        valet_pickup_price=day['valet_pickup_price'],
                        shuttle_delivery_price=day['shuttle_delivery_price'],
                        shuttle_pickup_price=day['shuttle_pickup_price'],
                        car_wash_price=day['car_wash_price'],
                        keep_key_price=day['keep_key_price'],
                    ) for day in reservation_days
                ]
                ReservationDay.objects.bulk_create(days_objs)
                # Update in-memory calendar
                for i_day in range(days):
                    day = res_start.date() + timedelta(days=i_day)
                    spot_calendar[day].add(available_spot.id)
                created_count += 1
                attempts += 1
        self.stdout.write(self.style.SUCCESS('Created up to 25 reservations of 5 days for each customer (August to November), only if there was availability.')) 