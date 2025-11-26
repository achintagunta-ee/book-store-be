from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Customer


class CustomerSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = Customer
        fields = ['email', 'password', 'password_confirm', 'first_name', 'last_name']
    
    def validate_email(self, value):
        if Customer.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('Email already registered')
        return value.lower()
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        customer = Customer.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return customer


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email', '').lower()
        password = data.get('password')
        
        if not email or not password:
            raise serializers.ValidationError('Email and password are required')
        
        customer = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        
        if not customer:
            raise serializers.ValidationError('Invalid email or password')
        
        if not customer.is_active:
            raise serializers.ValidationError('Account is deactivated')
        
        data['customer'] = customer
        return data


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'email', 'date_joined']