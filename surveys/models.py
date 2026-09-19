# surveys/models.py
from datetime import timedelta
import email
import hashlib
import os
import secrets
from django.utils import timezone
from django.db import models

# surveys/models.py
class Employee(models.Model):
    email_hash = models.CharField(max_length=256, unique=True)
    password_hash = models.CharField(max_length=256, null=True, blank=True)  # temporairement nullable
    department = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=50, blank=True)
    seniority = models.CharField(max_length=20, blank=True)
    work_mode = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    is_profile_completed = models.BooleanField(default=False)
    @staticmethod
    def generate_hash(email):
        return hashlib.sha256(email.encode()).hexdigest()

    def __str__(self):
        return self.email_hash
    
class PasswordResetToken(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True)  # sha256 hex = 64
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def create_for_employee(cls, employee: Employee, ttl_minutes: int = 30):
        raw_token = secrets.token_urlsafe(48)  # long et safe
        token_hash = cls.hash_token(raw_token)
        obj = cls.objects.create(
            employee=employee,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes)
        )
        return obj, raw_token

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at
    

class Survey(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class Question(models.Model):
    survey = models.ForeignKey("Survey", on_delete=models.CASCADE, related_name="questions")
    key = models.CharField(max_length=80)  # plus de null/blank
    text = models.TextField()
    question_type = models.CharField(max_length=30, default="text")
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("survey", "key")
        ordering = ["order"]


class SurveyResponse(models.Model):
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="survey_responses")
    survey = models.ForeignKey("Survey", on_delete=models.CASCADE, related_name="responses")
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["employee", "survey"], name="uniq_employee_survey"),
        ]

    def __str__(self):
        return f"Response #{self.id} - emp={self.employee_id} - survey={self.survey_id}"


class Answer(models.Model):
    response = models.ForeignKey("SurveyResponse", on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    value = models.TextField(blank=True, null=True)  # ✅ UNE seule colonne

    class Meta:
        unique_together = ("response", "question")  # ✅ une réponse par question


# surveys/models.py
class PostureMetric(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="posture_metrics")
    created_at = models.DateTimeField(auto_now_add=True)

    # Metrics temps réel
    total_time = models.FloatField(default=0)  # en secondes
    eye_closed_time = models.FloatField(default=0)
    blink_count = models.IntegerField(default=0)

    # Posture cumulée
    tete_penchee_time = models.FloatField(default=0)
    cou_vers_avant_time = models.FloatField(default=0)
    epaules_arrondies_time = models.FloatField(default=0)
    dos_courbe_time = models.FloatField(default=0)
    fatigue_visuelle_time = models.FloatField(default=0)

    # Score calculé
    score = models.FloatField(default=100)

    # Optionnel : lier à une vidéo
    video_file = models.FileField(upload_to="posture_videos/", null=True, blank=True)

    def __str__(self):
        return f"PostureMetric #{self.id} - emp={self.employee_id} - score={self.score:.1f}"

class EmployeeConversation(models.Model):
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE)
    survey = models.ForeignKey('Survey', on_delete=models.CASCADE)
    
    round_number = models.IntegerField(default=1)           # 1 = initial, 2,3,4 = follow-up
    created_at = models.DateTimeField(auto_now_add=True)
    
    # JSON complet de l'historique
    history = models.JSONField(default=dict)   # structure expliquée plus bas
    
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('employee', 'survey', 'round_number')
        ordering = ['round_number']

    def __str__(self):
        return f"Conversation {self.employee.id} - Round {self.round_number}"   




# surveys/models.py
from django.db import models


class VoiceAnalysis(models.Model):
    employee_id = models.IntegerField()
    transcript = models.TextField(blank=True)
    emotion = models.CharField(max_length=50, blank=True)
    emotion_confidence = models.FloatField(default=0)
    current_skills = models.JSONField(default=list)
    desired_skills = models.JSONField(default=list)
    recommended_position = models.CharField(max_length=200, blank=True)
    match_score = models.FloatField(default=0)
    
    # ✅ NOUVEAUX CHAMPS
    all_recommendations = models.JSONField(default=list)      # Les 3 recommandations
    validated_positions = models.JSONField(default=list)      # Postes validés par l'employé
    is_sent_to_hr = models.BooleanField(default=False)        # Envoyé aux RH ?
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Analyse #{self.id} - Employé {self.employee_id}"