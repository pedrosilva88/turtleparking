from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import login
from .serializers import (
    CustomerLoginSerializer, BusinessLoginSerializer, CustomerRegisterSerializer, BusinessRegisterSerializer,
    ReservationSerializer, VehicleSerializer
)
from .models import Reservation, Vehicle, ParkingSpot, ReservationDay, calculate_reservation_price
from rest_framework.permissions import IsAuthenticated
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse
from datetime import timedelta, date
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials.'})
    return render(request, 'login.html')

def logout_view(request):
    auth_logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    reservas = request.user.reservations.all()
    return render(request, 'dashboard.html', {'reservas': reservas})

@login_required
def create_reservation(request):
    from datetime import timedelta
    import math
    # Final confirmation of the summary
    if request.method == 'POST' and 'start_datetime' not in request.POST:
        if not request.user.is_authenticated:
            return redirect('login')
        reservation_data = request.session.get('reservation_data', {})
        extras = request.session.get('reservation_extras', {})
        vehicle_id = request.POST.get('vehicle')
        service_type = request.POST.get('service_type')
        vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
        start = reservation_data.get('start_datetime')
        end = reservation_data.get('end_datetime')
        from django.utils.dateparse import parse_datetime
        start_dt = parse_datetime(start) if start else None
        end_dt = parse_datetime(end) if end else None
        if not (start_dt and end_dt):
            return render(request, 'create_reservation.html', {'vehicles': request.user.vehicles.all(), 'reservation_data': reservation_data, 'error': 'Invalid dates.'})
        days = (end_dt.date() - start_dt.date()).days
        if days < 1:
            days = 1
        # Check availability for all days
        total_spots = ParkingSpot.objects.filter(is_active=True).count()
        daily_prices = []
        unavailable_days = []
        for i in range(days):
            day = start_dt.date() + timedelta(days=i)
            occupied = Reservation.objects.filter(
                start_datetime__date__lte=day,
                end_datetime__date__gte=day,
                status='active',
                parking_spot__isnull=False
            ).count()
            if occupied >= total_spots:
                unavailable_days.append(day)
            # Calculate daily price (without extras, rounded down)
            price = calculate_reservation_price(
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i),
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i+1),
                False, False, False
            )
            price = math.floor(price)
            daily_prices.append((day, price))
        if unavailable_days:
            return render(request, 'create_reservation.html', {
                'vehicles': request.user.vehicles.all(),
                'reservation_data': reservation_data,
                'error': f"No spots available on: {', '.join(str(d) for d in unavailable_days)}. Please choose another range."
            })
        # Calculate extras and create detailed history
        # Get current prices for extras
        from .models import PriceTable
        price_table = PriceTable.objects.first()
        valet_price = int(price_table.valet_price_per_day) if price_table else 5
        shuttle_price = 0  # Set if price exists
        car_wash_price = int(price_table.car_wash_price) if price_table else 20
        keep_key_price = int(price_table.keep_key_price_per_day) if price_table else 2
        total = 0
        reservation_days = []
        for i, (day, base_price) in enumerate(daily_prices):
            is_first = (i == 0)
            is_last = (i == days - 1)
            is_day_before_last = (i == days - 2)
            day_valet_delivery = extras.get('valet_entrega', False) and is_first
            day_valet_pickup = extras.get('valet_recolha', False) and is_last
            day_shuttle_delivery = extras.get('shuttle_entrega', False) and is_first
            day_shuttle_pickup = extras.get('shuttle_recolha', False) and is_last
            day_car_wash = extras.get('car_wash', False) and is_day_before_last
            day_keep_key = extras.get('keep_key', False)
            # Prices
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
        # Create reservation
        reserva = Reservation.objects.create(
            user=request.user,
            vehicle=vehicle,
            service_type=service_type,
            start_datetime=start_dt,
            end_datetime=end_dt,
            valet_entrega=extras.get('valet_entrega', False),
            valet_recolha=extras.get('valet_recolha', False),
            shuttle_entrega=extras.get('shuttle_entrega', False),
            shuttle_recolha=extras.get('shuttle_recolha', False),
            car_wash=extras.get('car_wash', False),
            keep_key=extras.get('keep_key', False),
            calculated_price=total,
            total_price=total,
        )
        # Create daily price history
        for day in reservation_days:
            ReservationDay.objects.create(
                reservation=reserva,
                date=day['date'],
                price=day['price'],
                valet_delivery_price=day['valet_delivery_price'],
                valet_pickup_price=day['valet_pickup_price'],
                shuttle_delivery_price=day['shuttle_delivery_price'],
                shuttle_pickup_price=day['shuttle_pickup_price'],
                car_wash_price=day['car_wash_price'],
                keep_key_price=day['keep_key_price'],
            )
        # Clear session
        if 'reservation_data' in request.session:
            del request.session['reservation_data']
        if 'reservation_extras' in request.session:
            del request.session['reservation_extras']
        return redirect('dashboard')
    # If coming from homepage form
    if request.method == 'POST':
        arrival_date = request.POST.get('arrival_date')
        arrival_time = request.POST.get('arrival_time')
        departure_date = request.POST.get('departure_date')
        departure_time = request.POST.get('departure_time')
        # If coming from traditional form (authenticated)
        vehicle_id = request.POST.get('vehicle')
        service_type = request.POST.get('service_type')
        # If user is authenticated, can create full reservation
        if request.user.is_authenticated:
            if vehicle_id and service_type:
                # Traditional reservation (dashboard)
                from .models import Vehicle
                vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
                Reservation.objects.create(
                    user=request.user,
                    vehicle=vehicle,
                    service_type=service_type,
                    start_datetime=request.POST.get('start_datetime'),
                    end_datetime=request.POST.get('end_datetime'),
                )
                return redirect('dashboard')
            elif arrival_date and arrival_time and departure_date and departure_time:
                # Quick reservation (homepage)
                # Redirect to choose vehicle and service
                request.session['reservation_data'] = {
                    'start_datetime': f"{arrival_date}T{arrival_time}",
                    'end_datetime': f"{departure_date}T{departure_time}",
                }
                return redirect('create-reservation')
        else:
            # Not authenticated: save data in session and ask for login
            if arrival_date and arrival_time and departure_date and departure_time:
                request.session['reservation_data'] = {
                    'start_datetime': f"{arrival_date}T{arrival_time}",
                    'end_datetime': f"{departure_date}T{departure_time}",
                }
                return redirect('login')
    # GET or after login: if there is data in session, ask for vehicle and service
    reservation_data = request.session.get('reservation_data')
    vehicles = None
    if request.user.is_authenticated:
        vehicles = request.user.vehicles.all()
    return render(request, 'create_reservation.html', {'vehicles': vehicles, 'reservation_data': reservation_data})

class CustomerLoginView(APIView):
    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            return Response({'detail': 'Login successful (customer).'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessLoginView(APIView):
    def post(self, request):
        serializer = BusinessLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            return Response({'detail': 'Login successful (business).'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomerRegisterView(APIView):
    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({'detail': 'Registration successful (customer).'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessRegisterView(APIView):
    def post(self, request):
        serializer = BusinessRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({'detail': 'Registration successful (business).'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReservationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reservations = Reservation.objects.filter(user=request.user)
        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ReservationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReservationCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            reservation = Reservation.objects.get(pk=pk, user=request.user)
        except Reservation.DoesNotExist:
            return Response({'detail': 'Reservation not found.'}, status=status.HTTP_404_NOT_FOUND)
        if reservation.status == 'cancelled':
            return Response({'detail': 'Reservation is already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        reservation.status = 'cancelled'
        reservation.save()
        return Response({'detail': 'Reservation cancelled successfully.'}, status=status.HTTP_200_OK)

class VehicleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vehicles = Vehicle.objects.filter(user=request.user)
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = VehicleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VehicleDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, user=request.user)
        except Vehicle.DoesNotExist:
            return Response({'detail': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)
        vehicle.delete()
        return Response({'detail': 'Vehicle removed successfully.'}, status=status.HTTP_204_NO_CONTENT)

@login_required
def vehicles_view(request):
    if request.method == 'POST':
        # Delete vehicle (from vehicles.html form)
        vehicle_id = request.POST.get('vehicle_id') or request.POST.get('vehicle') or request.POST.get('pk')
        if vehicle_id:
            Vehicle.objects.filter(id=vehicle_id, user=request.user).delete()
            messages.success(request, 'Vehicle deleted.')
            return redirect('vehicles')
    vehicles = request.user.vehicles.all()
    return render(request, 'vehicles.html', {'vehicles': vehicles})

@login_required
def create_vehicle_view(request):
    if request.method == 'POST':
        plate = request.POST.get('plate')
        model = request.POST.get('model')
        brand = request.POST.get('brand')
        color = request.POST.get('color')
        if plate and model:
            Vehicle.objects.create(user=request.user, plate=plate, model=model, brand=brand, color=color)
            return redirect('vehicles')
    return render(request, 'create_vehicle.html')

@login_required
def delete_vehicle_view(request, pk):
    Vehicle.objects.filter(id=pk, user=request.user).delete()
    return redirect('vehicles')

@login_required
def reservation_detail_view(request, pk):
    try:
        reservation = Reservation.objects.get(pk=pk, user=request.user)
    except Reservation.DoesNotExist:
        return redirect('dashboard')
    return render(request, 'reservation_detail.html', {'reservation': reservation})

@require_http_methods(["GET", "POST"])
def register_view(request):
    User = get_user_model()
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        profile_picture = request.FILES.get('profile_picture')
        if username and email and password and name:
            user = User.objects.create_user(username=username, email=email, password=password, name=name, phone=phone)
            if profile_picture:
                user.profile_picture = profile_picture
                user.save()
            return redirect('login')
    return render(request, 'register.html')

def home_view(request):
    return render(request, 'home.html')

def contacts_view(request):
    return render(request, 'contacts.html')

def people_view(request):
    return render(request, 'people.html')

def legal_view(request):
    return render(request, 'legal.html')

def reservation_summary_view(request):
    from .models import PriceTable
    # If POST from homepage, save dates in session
    if request.method == 'POST' and 'arrival_date' in request.POST:
        arrival_date = request.POST.get('arrival_date')
        arrival_time = request.POST.get('arrival_time')
        departure_date = request.POST.get('departure_date')
        departure_time = request.POST.get('departure_time')
        if arrival_date and arrival_time and departure_date and departure_time:
            request.session['reservation_data'] = {
                'start_datetime': f"{arrival_date}T{arrival_time}",
                'end_datetime': f"{departure_date}T{departure_time}",
            }
        return redirect('reservation-summary')
    # If POST from extras
    if request.method == 'POST' and (
        'valet_entrega' in request.POST or 'valet_recolha' in request.POST or 'shuttle_entrega' in request.POST or 'shuttle_recolha' in request.POST or 'car_wash' in request.POST or 'keep_key' in request.POST):
        valet_entrega = bool(request.POST.get('valet_entrega'))
        valet_recolha = bool(request.POST.get('valet_recolha'))
        shuttle_entrega = bool(request.POST.get('shuttle_entrega'))
        shuttle_recolha = bool(request.POST.get('shuttle_recolha'))
        car_wash = bool(request.POST.get('car_wash'))
        keep_key = bool(request.POST.get('keep_key'))
        reservation_data = request.session.get('reservation_data', {})
        start = reservation_data.get('start_datetime')
        end = reservation_data.get('end_datetime')
        start_dt = parse_datetime(start) if start else None
        end_dt = parse_datetime(end) if end else None
        days_breakdown = []
        total = 0
        if start_dt and end_dt:
            dias = (end_dt.date() - start_dt.date()).days
            if dias < 1:
                dias = 1
            price_table = PriceTable.objects.first()
            valet_price = int(price_table.valet_price_per_day) if price_table else 5
            shuttle_price = 0  # Definir se existir preço
            car_wash_price = int(price_table.car_wash_price) if price_table else 20
            keep_key_price = int(price_table.keep_key_price_per_day) if price_table else 2
            for i in range(dias):
                dia = start_dt.date() + timedelta(days=i)
                is_first = (i == 0)
                is_last = (i == dias - 1)
                is_day_before_last = (i == dias - 2)
                day_valet_entrega = valet_entrega and is_first
                day_valet_recolha = valet_recolha and is_last
                day_shuttle_entrega = shuttle_entrega and is_first
                day_shuttle_recolha = shuttle_recolha and is_last
                day_car_wash = car_wash and is_day_before_last
                day_keep_key = keep_key
                # Preços
                base_price = calculate_reservation_price(
                    start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i),
                    start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i+1),
                    False, False, False
                )
                import math
                base_price = math.floor(base_price)
                v_entrega = valet_price if day_valet_entrega else 0
                v_recolha = valet_price if day_valet_recolha else 0
                s_entrega = shuttle_price if day_shuttle_entrega else 0
                s_recolha = shuttle_price if day_shuttle_recolha else 0
                c_wash = car_wash_price if day_car_wash else 0
                k_key = keep_key_price if day_keep_key else 0
                day_total = base_price + v_entrega + v_recolha + s_entrega + s_recolha + c_wash + k_key
                total += day_total
                days_breakdown.append({
                    'date': dia,
                    'base_price': base_price,
                    'valet_entrega': v_entrega,
                    'valet_recolha': v_recolha,
                    'shuttle_entrega': s_entrega,
                    'shuttle_recolha': s_recolha,
                    'car_wash': c_wash,
                    'keep_key': k_key,
                    'total': day_total,
                })
        request.session['reservation_extras'] = {
            'valet_entrega': valet_entrega,
            'valet_recolha': valet_recolha,
            'shuttle_entrega': shuttle_entrega,
            'shuttle_recolha': shuttle_recolha,
            'car_wash': car_wash,
            'keep_key': keep_key,
            'calculated_price': total,
        }
        return render(request, 'reservation_summary.html', {
            'reservation_data': reservation_data,
            'valet_entrega': valet_entrega,
            'valet_recolha': valet_recolha,
            'shuttle_entrega': shuttle_entrega,
            'shuttle_recolha': shuttle_recolha,
            'car_wash': car_wash,
            'keep_key': keep_key,
            'calculated_price': total,
            'show_confirm': True,
            'days_breakdown': days_breakdown,
        })
    # GET: show initial summary
    reservation_data = request.session.get('reservation_data', {})
    start = reservation_data.get('start_datetime')
    end = reservation_data.get('end_datetime')
    start_dt = parse_datetime(start) if start else None
    end_dt = parse_datetime(end) if end else None
    days_breakdown = []
    total = 0
    if start_dt and end_dt:
        dias = (end_dt.date() - start_dt.date()).days
        if dias < 1:
            dias = 1
        price_table = PriceTable.objects.first()
        valet_price = int(price_table.valet_price_per_day) if price_table else 5
        shuttle_price = 0
        car_wash_price = int(price_table.car_wash_price) if price_table else 20
        keep_key_price = int(price_table.keep_key_price_per_day) if price_table else 2
        for i in range(dias):
            dia = start_dt.date() + timedelta(days=i)
            base_price = calculate_reservation_price(
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i),
                start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i+1),
                False, False, False
            )
            import math
            base_price = math.floor(base_price)
            days_breakdown.append({
                'date': dia,
                'base_price': base_price,
                'valet_entrega': 0,
                'valet_recolha': 0,
                'shuttle_entrega': 0,
                'shuttle_recolha': 0,
                'car_wash': 0,
                'keep_key': 0,
                'total': base_price,
            })
            total += base_price
    return render(request, 'reservation_summary.html', {
        'reservation_data': reservation_data,
        'valet_entrega': False,
        'valet_recolha': False,
        'shuttle_entrega': False,
        'shuttle_recolha': False,
        'car_wash': False,
        'keep_key': False,
        'calculated_price': total,
        'show_confirm': False,
        'days_breakdown': days_breakdown,
    })

@csrf_exempt
def daily_prices_api(request):
    # Expects GET with ?start=YYYY-MM-DD&end=YYYY-MM-DD
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    if not start_str or not end_str:
        return JsonResponse({'error': 'Missing start or end'}, status=400)
    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except Exception:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    days = (end_date - start_date).days + 1
    prices = {}
    for i in range(days):
        d = start_date + timedelta(days=i)
        # Price for this day (without extras)
        from .models import PriceTable, ParkingSpot, Reservation
        total_spots = ParkingSpot.objects.filter(is_active=True).count()
        occupied = Reservation.objects.filter(
            start_datetime__date__lte=d,
            end_datetime__date__gte=d,
            status='active',
            parking_spot__isnull=False
        ).count()
        if total_spots == 0 or occupied >= total_spots:
            print(f"No spots available for {d.isoformat()} - {occupied}/{total_spots}")
            prices[d.isoformat()] = None
        else:
            price = calculate_reservation_price(
                datetime.combine(d, datetime.min.time()),
                datetime.combine(d, datetime.min.time()) + timedelta(days=1),
                valet=False, car_wash=False, keep_key=False
            )
            prices[d.isoformat()] = price
    return JsonResponse(prices)
