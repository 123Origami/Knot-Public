from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import models
from .models import CustomUser, EmailVerificationToken, PasswordResetToken
import re

class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data"""
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                  'phone_number', 'profile_picture', 'bio', 'location',
                  'verification_level', 'average_rating', 'total_reviews',
                  'successful_bookings', 'cancelled_bookings', 'date_joined']
        read_only_fields = ['verification_level', 'average_rating', 'total_reviews',
                            'successful_bookings', 'cancelled_bookings', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name', 'phone_number']
    
    def validate(self, data):
        # Password match
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match")

        # Password complexity: at least one uppercase, one lowercase, one digit, one special
        password = data.get('password') or ''
        complexity_re = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')
        if not complexity_re.match(password):
            raise serializers.ValidationError(
                "Password must be at least 8 characters and include uppercase, lowercase, digit, and special character."
            )

        # Username uniqueness
        username = (data.get('username') or '').strip()
        if username and CustomUser.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({'username': 'Username already exists'})

        # Name fields cannot be purely numeric
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        if first_name and first_name.isdigit():
            raise serializers.ValidationError({'first_name': 'First name cannot be only numbers'})
        if last_name and last_name.isdigit():
            raise serializers.ValidationError({'last_name': 'Last name cannot be only numbers'})

        # Phone validation: must be exactly 10 digits and unique if provided
        phone = (data.get('phone_number') or '').strip()
        if phone:
            if not phone.isdigit() or len(phone) != 10:
                raise serializers.ValidationError({'phone_number': 'Phone number must be exactly 10 digits'})
            if CustomUser.objects.filter(phone_number=phone).exists():
                raise serializers.ValidationError({'phone_number': 'Phone number already in use'})

        return data
    
    def create(self, validated_data):
        # Remove password2 and use create_user to properly hash password
        validated_data.pop('password2', None)
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                candidate = CustomUser.objects.filter(
                    models.Q(username__iexact=username) | models.Q(email__iexact=username)
                ).first()
                if candidate and candidate.check_password(password):
                    # Keep disabled verified accounts blocked, but allow unverified users.
                    if candidate.is_active or not candidate.email_verified:
                        user = candidate

            if user:
                if not user.is_active and user.email_verified:
                    raise serializers.ValidationError("User account is disabled.")
                data['user'] = user
            else:
                raise serializers.ValidationError("Unable to log in with provided credentials.")
        else:
            raise serializers.ValidationError("Must include 'username' and 'password'.")
        
        return data


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'bio', 'location', 'profile_picture']