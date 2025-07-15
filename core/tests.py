from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Profile, Vehicle, Reservation

# Create your tests here.

class AuthTests(APITestCase):
    def test_customer_register_and_login(self):
        # Cadastro
        url = reverse('customer-register')
        data = {
            'username': 'testuser',
            'email': 'testuser@email.com',
            'name': 'Test User',
            'password': 'senha123',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Login
        url = reverse('customer-login')
        data = {'username_or_email': 'testuser', 'password': 'senha123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class ReservationTests(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(username='cliente2', email='cliente2@email.com', name='Cliente Dois', password='senha123', role='customer')
        self.vehicle = Vehicle.objects.create(user=self.user, plate='ABC1234', model='Fiat Uno', color='Branco')
    def test_create_reservation(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('reservation-list-create')
        data = {
            'vehicle': self.vehicle.id,
            'service_type': 'standard',
            'start_datetime': '2024-07-01T10:00:00Z',
            'end_datetime': '2024-07-02T10:00:00Z',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reservation.objects.count(), 1)
