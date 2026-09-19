from django.db import models
from django.utils import timezone
from surveys.models import Employee
class VideoUpload(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("PROCESSING", "PROCESSING"),
        ("DONE", "DONE"),
        ("FAILED", "FAILED"),
    ]

    employee = models.ForeignKey("surveys.Employee", on_delete=models.CASCADE, related_name="video_uploads")
    video_file = models.FileField(upload_to="employee_videos/%Y/%m/%d/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    fps_used = models.IntegerField(default=10)
    duration_sec = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"VideoUpload #{self.id} emp={self.employee_id} status={self.status}"


class VideoAnalysisResult(models.Model):
    upload = models.OneToOneField(VideoUpload, on_delete=models.CASCADE, related_name="result")

    posture_score = models.FloatField(default=0)
    posture_status = models.CharField(max_length=20, default="UNKNOWN")  # GOOD/OK/BAD/UNKNOWN
    bad_posture_pct = models.FloatField(default=0)

    blink_rate_per_min = models.FloatField(null=True, blank=True)
    perclos = models.FloatField(null=True, blank=True)

    repetitive_motion_score = models.FloatField(null=True, blank=True)
    summary_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)


class VideoSegment(models.Model):
    SEGMENT_TYPES = [
        ("BAD_POSTURE", "BAD_POSTURE"),
        ("HIGH_BLINK", "HIGH_BLINK"),
        ("REPETITIVE_MOTION", "REPETITIVE_MOTION"),
    ]

    upload = models.ForeignKey(VideoUpload, on_delete=models.CASCADE, related_name="segments")
    type = models.CharField(max_length=30, choices=SEGMENT_TYPES)
    start_sec = models.FloatField()
    end_sec = models.FloatField()
    severity = models.IntegerField(default=3)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)


class RealtimeMetrics(models.Model):
    employee = models.ForeignKey("surveys.Employee", on_delete=models.CASCADE)

    total_time = models.FloatField(default=0)
    eye_closed_time = models.FloatField(default=0)
    blink_count = models.IntegerField(default=0)


# --- NOUVEAUX CHAMPS AJOUTÉS POUR LA FATIGUE VISUELLE ---
    ear_history = models.JSONField(default=list)  # Stocke le flux EAR pour le graphique
    blink_rate_per_min = models.FloatField(default=0)
    perclos = models.FloatField(default=0)
    visual_fatigue_score = models.FloatField(default=0)
    microsleep_count = models.IntegerField(default=0)
# --------------------------------------------------------


    posture_time = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now=True)
    