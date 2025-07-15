from django.urls import path
from .views import (
    CustomerLoginView, BusinessLoginView, CustomerRegisterView, BusinessRegisterView,
    ReservationListCreateView, ReservationCancelView,
    login_view, logout_view, dashboard, create_reservation,
    vehicles_view, create_vehicle_view, delete_vehicle_view, reservation_detail_view, register_view, home_view,
    contacts_view, people_view, legal_view, reservation_summary_view, daily_prices_api
)

urlpatterns = [
    path('', home_view, name='home'),
    path('auth/login/customer/', CustomerLoginView.as_view(), name='customer-login'),
    path('auth/login/business/', BusinessLoginView.as_view(), name='business-login'),
    path('auth/register/customer/', CustomerRegisterView.as_view(), name='customer-register'),
    path('auth/register/business/', BusinessRegisterView.as_view(), name='business-register'),
    path('reservations/', ReservationListCreateView.as_view(), name='reservation-list-create'),
    path('reservations/<int:pk>/cancel/', ReservationCancelView.as_view(), name='reservation-cancel'),
    path('vehicles/', vehicles_view, name='vehicles'),
    path('vehicles/create/', create_vehicle_view, name='create-vehicle'),
    path('vehicles/<int:pk>/delete/', delete_vehicle_view, name='vehicle-delete'),
    path('reservations/<int:pk>/', reservation_detail_view, name='reservation-detail'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('create-reservation/', create_reservation, name='create-reservation'),
    path('register/', register_view, name='register'),
    path('contacts/', contacts_view, name='contacts'),
    path('people/', people_view, name='people'),
    path('legal/', legal_view, name='legal'),
    path('reservation-summary/', reservation_summary_view, name='reservation-summary'),
    path('api/daily-prices/', daily_prices_api, name='daily-prices-api'),
] 