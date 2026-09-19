from django.contrib import admin
from .models import Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email_hash",
        "department",
        "role",
        "seniority",
        "work_mode",
        "is_admin", 
        "created_at"
    )
    list_filter = (
        "department", 
        "role", 
        "work_mode",
        "is_admin"
        )
    search_fields = (
        "email_hash",)