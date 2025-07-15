from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import Profile, Reservation, Vehicle, ParkingSpot
from django.db import models

class CustomerLoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        username_or_email = data.get('username_or_email')
        password = data.get('password')
        user = Profile.objects.filter(role='customer').filter(
            models.Q(username=username_or_email) | models.Q(email=username_or_email)
        ).first()
        if user is None:
            raise serializers.ValidationError('Usuário não encontrado ou não é cliente.')
        if not user.check_password(password):
            raise serializers.ValidationError('Senha incorreta.')
        if not user.is_active:
            raise serializers.ValidationError('Usuário inativo.')
        data['user'] = user
        return data

class BusinessLoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        username_or_email = data.get('username_or_email')
        password = data.get('password')
        user = Profile.objects.filter(role='business').filter(
            models.Q(username=username_or_email) | models.Q(email=username_or_email)
        ).first()
        if user is None:
            raise serializers.ValidationError('Usuário não encontrado ou não é funcionário/business.')
        if not user.check_password(password):
            raise serializers.ValidationError('Senha incorreta.')
        if not user.is_active:
            raise serializers.ValidationError('Usuário inativo.')
        data['user'] = user
        return data

class CustomerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = Profile
        fields = ['username', 'email', 'name', 'phone', 'profile_picture', 'password']

    def create(self, validated_data):
        user = Profile.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            name=validated_data['name'],
            phone=validated_data.get('phone'),
            profile_picture=validated_data.get('profile_picture'),
            role='customer',
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class BusinessRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = Profile
        fields = ['username', 'email', 'name', 'phone', 'profile_picture', 'password']

    def create(self, validated_data):
        user = Profile.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            name=validated_data['name'],
            phone=validated_data.get('phone'),
            profile_picture=validated_data.get('profile_picture'),
            role='business',
        )
        user.set_password(validated_data['password'])
        user.save()
        return user 

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'id', 'user', 'vehicle', 'parking_spot', 'employee', 'service_type',
            'start_datetime', 'end_datetime', 'status', 'total_price'
        ]
        read_only_fields = ['user', 'status', 'total_price'] 

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'user', 'plate', 'model', 'color']
        read_only_fields = ['user'] 