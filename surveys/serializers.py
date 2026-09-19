# surveys/serializers.py
from rest_framework import serializers
from .models import Employee
import hashlib

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = "__all__"

    def create(self, validated_data):
        # Hash du mot de passe
        password = validated_data.pop('password_hash')
        validated_data['password_hash'] = hashlib.sha256(password.encode()).hexdigest()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'password_hash' in validated_data:
            password = validated_data.pop('password_hash')
            instance.password_hash = hashlib.sha256(password.encode()).hexdigest()
        return super().update(instance, validated_data)
