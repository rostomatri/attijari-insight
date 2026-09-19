# surveys/urls.py
from django.contrib import admin
from django.urls import path,include
from .views import ValidatePositionsView, VoiceAnalysisListView, VoiceAnalysisView, anonymous_login_api, confirm_password_reset,request_password_reset, create_admin, delete_employee, list_employees, login, save_followup_response, save_survey_response, update_employee
from .views import anonymous_login
from .views import auth_employee
from .views import complete_profile
from .views import register_employee, login,save_survey_response, get_active_survey, my_survey_response,analytics_summary, my_analytics_summary, get_followup_questionnaire
from django.conf import settings
from django.conf.urls.static import static

from surveys import views
from vision.views import  all_vision_history,vision_history,all_employee_history, analyze_frame, daily_report, employee_history, reset_metrics, upload_video, video_status, video_result
urlpatterns = [
    path('admin/', admin.site.urls, name='django_admin'),  # Correction du namespace pour éviter les conflits
    
    path("api/anonymous-login/", anonymous_login_api),
    path("api/anonymous-login/", anonymous_login, name="anonymous_login"),
    
    #path("api/login/", auth_employee),  # Redirige vers auth_employee pour gérer la connexion
    path("api/register/", register_employee, name="register"),
    path("api/auth/", auth_employee, name="auth"),
    path("api/complete-profile/", complete_profile, name="complete_profile"),
    
    path("api/employees/", list_employees, name="list_employees"),
    path("api/employees/<int:employee_id>/", update_employee, name="update_employee"),
    path("api/employees/<int:employee_id>/delete/", delete_employee, name="delete_employee"),
    path("api/create-admin/", create_admin, name="create_admin"),
    path("api/password-reset/request/", request_password_reset, name="password_reset_request"),
    path("api/password-reset/confirm/", confirm_password_reset, name="password_reset_confirm"),
    path("api/save-survey/", save_survey_response, name="save_survey"),
    path("api/active-survey/", get_active_survey, name="active-survey"),
    path("api/my-survey-response/", my_survey_response, name="my_survey_response"),
    path("api/analytics/summary/", analytics_summary, name="analytics_summary"),
    path("api/analytics/my-summary/", my_analytics_summary,name="my_analytics_summary"),
    path('api/followup-questionnaire/',get_followup_questionnaire, name='followup-questionnaire'),
    path('api/save-followup-response/', save_followup_response, name='save_followup_response'),
    path("api/videos/upload/", upload_video),
    path("api/videos/<int:upload_id>/status/", video_status),
    path("api/videos/<int:upload_id>/result/", video_result),
    path("api/analyze-frame/", analyze_frame),
    path('api/history/<int:employee_id>/', employee_history),
    path('api/all-history/', all_employee_history),
    path('api/reset-metrics/', reset_metrics),
    path('api/daily-report/<int:employee_id>/', daily_report),
    path('api/employee-profile/', views.get_employee_profile, name='get_employee_profile'),
    path('api/voice/analyze/', VoiceAnalysisView.as_view(), name='voice-analyze'),
    path('api/voice/all-analyses/', VoiceAnalysisListView.as_view(), name='voice-history'),
    path('api/voice/validate-positions/', ValidatePositionsView.as_view(), name='validate-positions'),  # ✅ NOUVEAU
    path('api/vision-history/<int:employee_id>/',vision_history),
    path('api/all-vision-history/',all_vision_history),
]
# ✅ Static & Media seulement en DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    