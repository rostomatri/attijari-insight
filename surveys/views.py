# surveys/views.py
import email
import json
import threading
from urllib import request, response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from surveys.analytics.risk_cache import update_risk_cache_for_response
from .models import Employee
from django.views.decorators.csrf import csrf_exempt
import hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Employee
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import PasswordResetToken
import os
import csv
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone

from .models import Employee, Survey, Question, SurveyResponse, Answer, EmployeeConversation
from .analytics.builder import rebuild_analytics_snapshot
from surveys.analytics.trigger import trigger_rebuild_if_needed
from surveys.analytics.incremental_nlp import update_nlp_state_for_response
from surveys.analytics.risk_cache import load_risk_cache, rebuild_risk_cache_full
from .analytics.adaptive_questionnaire import generate_next_questionnaire

logger = logging.getLogger(__name__)

# les fonctions ou fichiers de test
# login
# hash_email
# hash_password
# serializers.py (tant que pas DRF)
# anonymous_login et/ou anonymous_login_api 

@csrf_exempt
def anonymous_login(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)


    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")


        if not email:
            return JsonResponse(
                {"message": "Email requis"},
                status=400
            )
        email_hash = Employee.generate_hash(email)


        # on ne crée PAS encore l’employé
        request.session["email_hash"] = email_hash


        return JsonResponse({
        "message": "Connexion anonyme acceptée"
        }, status=200)


    return JsonResponse({"error": "Méthode non autorisée"}, status=405)


@csrf_exempt
def anonymous_login_api(request):
    if request.method == "POST":
        data = json.loads(request.body)

        email = data["email"]
        email_hash = Employee.generate_hash(email)

        employee, created = Employee.objects.get_or_create(
            email_hash=email_hash,
            defaults={
                "department": data["department"],
                "role": data["role"],
                "seniority": data["seniority"],
                "work_mode": data["work_mode"],
            }
        )

        request.session["employee_id"] = employee.id

        return JsonResponse({
            "message": "Connexion anonyme réussie",
            "employee_id": employee.id
        })
    


@csrf_exempt
def auth_employee(request):
    if request.method != "POST":
        return JsonResponse({"message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return JsonResponse({"message": "Email et mot de passe requis"}, status=400)

        email_hash = hash_string(email)
        password_hash = hash_string(password)

        # Cherche l'employé
        try:
            employee = Employee.objects.get(email_hash=email_hash)
        except Employee.DoesNotExist:
            return JsonResponse({"message": "Utilisateur non trouvé"}, status=404)

        if employee.password_hash != password_hash:
            return JsonResponse({"message": "Mot de passe incorrect"}, status=401)

        # Pour admin, on ne teste jamais le profil
        if employee.is_admin:
            return JsonResponse({
                "message": "Connexion réussie",
                "is_admin": True,
                "profile_completed": True,
                "redirect": "admin-dashboard",
                "employee_id": employee.id
            })

        # Pour utilisateur normal, vérifie si le profil est complété
        profile_completed = employee.is_profile_completed
        redirect_target = "complete-profile" if not profile_completed else "user-dashboard"

        return JsonResponse({
            "message": "Connexion réussie",
            "is_admin": False,
            "profile_completed": profile_completed,
            "redirect": redirect_target,
            "employee_id": employee.id
        })

    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)

@csrf_exempt
def complete_profile(request):
    if request.method != "POST":
        return JsonResponse({"message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        employee_id = data.get("employee_id")
        profile_data = data.get("profile")

        employee = Employee.objects.get(id=employee_id)

        # Met à jour les champs
        employee.department = profile_data.get("department", "")
        employee.role = profile_data.get("role", "")
        employee.seniority = profile_data.get("seniority", "")
        employee.work_mode = profile_data.get("work_mode", "")

        # Marque le profil comme complété
        employee.is_profile_completed = True
        employee.save()

        return JsonResponse({"message": "Profil complété avec succès", "profile_completed": True})

    except Employee.DoesNotExist:
        return JsonResponse({"message": "Utilisateur non trouvé"}, status=404)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)


def hash_email(email):
    return hashlib.sha256(email.encode()).hexdigest()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
def hash_string(s):
    return hashlib.sha256(s.encode()).hexdigest()
@csrf_exempt
def register_employee(request):
    print("=== fonction register_employee appelée ===")
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({"message": "Email et mot de passe requis"}, status=400)

            email_hash = hash_string(email)
            password_hash = hash_string(password)

            # Vérifie si l'email existe déjà
            if Employee.objects.filter(email_hash=email_hash).exists():
                return JsonResponse({"message": "Email déjà utilisé"}, status=400)

            employee = Employee.objects.create(
                email_hash=email_hash,
                password_hash=password_hash
            )

            return JsonResponse({
                "message": "Inscription réussie, veuillez compléter votre profil",
                "employee_id": employee.id
            })
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    return JsonResponse({"message": "Méthode non autorisée"}, status=405)

@csrf_exempt
def login(request):
    print("=== fonction login appelée ===")
    if request.method == "POST":
        data = json.loads(request.body)
        email_hash = hash_email(data["email"])
        password_hash = hash_password(data["password"])

        try:
            employee = Employee.objects.get(email_hash=email_hash)
            if employee.password_hash == password_hash:
                return JsonResponse({
                    "message": "Connexion réussie",
                    "is_admin": employee.is_admin,  # Ajout de is_admin
                    "redirect": "admin-dashboard" if employee.is_admin else "user_dashboard"
                })
            else:
                return JsonResponse({"message": "Mot de passe incorrect"}, status=400)
        except Employee.DoesNotExist:
            return JsonResponse({"message": "Utilisateur non trouvé"}, status=404)

    return JsonResponse({"message": "Méthode non autorisée"}, status=405)

@csrf_exempt
def create_admin(request):
    print("=== fonction create_admin appelée ===")
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({"message": "Email et mot de passe requis"}, status=400)

            email_hash = hash_string(email)
            password_hash = hash_string(password)

            # Vérifie si l’email existe déjà
            if Employee.objects.filter(email_hash=email_hash).exists():
                return JsonResponse({"message": "Email déjà utilisé"}, status=400)

            employee = Employee.objects.create(
                email_hash=email_hash,
                password_hash=password_hash,
                is_admin=True,
                is_profile_completed=True  # admin n’a pas besoin de compléter le profil
            )

            return JsonResponse({
                "message": "Administrateur créé avec succès",
                "employee_id": employee.id
            })

        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)


@csrf_exempt
def list_employees(request):
    if request.method == "GET":
        # Tous les employés non-admin
        employees = Employee.objects.filter(is_admin=False).values(
            "id", "email_hash", "department", "role", "seniority", "work_mode"
        )
        
        # Tous les admins, seulement l'email
        admins = Employee.objects.filter(is_admin=True).values(
            "email_hash",
        )
        
        # Renvoie les deux tableaux
        return JsonResponse({
            "employees": list(employees),
            "admins": list(admins)
        }, safe=False)
    
    return JsonResponse({"message": "Méthode non autorisée"}, status=405)

@csrf_exempt
def update_employee(request, employee_id):
    if request.method == "PUT":
        data = json.loads(request.body)
        try:
            employee = Employee.objects.get(id=employee_id)
            employee.department = data.get("department", employee.department)
            employee.role = data.get("role", employee.role)
            employee.seniority = data.get("seniority", employee.seniority)
            employee.work_mode = data.get("work_mode", employee.work_mode)
            employee.is_admin = data.get("is_admin", employee.is_admin)
            employee.save()
            return JsonResponse({"message": "Employé mis à jour"})
        except Employee.DoesNotExist:
            return JsonResponse({"message": "Employé non trouvé"}, status=404)
    return JsonResponse({"message": "Méthode non autorisée"}, status=405)

@csrf_exempt
def delete_employee(request, employee_id):
    if request.method == "DELETE":
        try:
            employee = Employee.objects.get(id=employee_id)
            employee.delete()
            return JsonResponse({"message": "Employé supprimé"})
        except Employee.DoesNotExist:
            return JsonResponse({"message": "Employé non trouvé"}, status=404)
    return JsonResponse({"message": "Méthode non autorisée"}, status=405)

@csrf_exempt
def request_password_reset(request):
    if request.method != "POST":
        return JsonResponse({"message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")

        # Toujours réponse neutre (anti-enumeration)
        generic_msg = {"message": "Si ce compte existe, un email de réinitialisation a été envoyé."}

        if not email:
            return JsonResponse(generic_msg, status=200)

        email_hash = hash_string(email)

        try:
            employee = Employee.objects.get(email_hash=email_hash)
        except Employee.DoesNotExist:
            return JsonResponse(generic_msg, status=200)

        # (Optionnel) invalider anciens tokens non utilisés
        PasswordResetToken.objects.filter(employee=employee, used_at__isnull=True, expires_at__gt=timezone.now()).update(used_at=timezone.now())

        token_obj, raw_token = PasswordResetToken.create_for_employee(employee, ttl_minutes=30)

        reset_link = f"http://localhost:3000/reset-password?token={raw_token}"
        # (adapte le domaine/port à ton front)

        send_mail(
            subject="Réinitialisation de votre mot de passe",
            message=f"Bonjour,\n\nCliquez sur ce lien pour réinitialiser votre mot de passe (valide 30 min):\n{reset_link}\n\nSi vous n'êtes pas à l'origine, ignorez cet email.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse(generic_msg, status=200)

    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)
@csrf_exempt
def confirm_password_reset(request):
    if request.method != "POST":
        return JsonResponse({"message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        token = data.get("token")
        new_password = data.get("new_password")

        if not token or not new_password:
            return JsonResponse({"message": "Token et nouveau mot de passe requis"}, status=400)

        token_hash = PasswordResetToken.hash_token(token)

        try:
            t = PasswordResetToken.objects.select_related("employee").get(token_hash=token_hash)
        except PasswordResetToken.DoesNotExist:
            return JsonResponse({"message": "Token invalide"}, status=400)

        if not t.is_valid():
            return JsonResponse({"message": "Token expiré ou déjà utilisé"}, status=400)

        employee = t.employee
        employee.password_hash = hash_string(new_password)
        employee.save()

        t.used_at = timezone.now()
        t.save()

        return JsonResponse({"message": "Mot de passe réinitialisé avec succès"}, status=200)

    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)

# @csrf_exempt
# def save_survey_response(request):
#     if request.method != "POST":
#         return JsonResponse({"message": "Method not allowed"}, status=405)

#     try:
#         payload = json.loads(request.body.decode("utf-8"))
#     except Exception:
#         return JsonResponse({"message": "Invalid JSON"}, status=400)

#     # ✅ chemin vers data/synthetic_data.csv (data est à la racine)
#     BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # => pfe/
#     csv_path = os.path.join(BASE_DIR, "analytics", "synthetic_data.csv")

#     # ✅ les colonnes exactement comme ton CSV
#     headers = [
#         'Quel est votre niveau de stress au travail ?(1 étant "pas du tout stressé" , 5 étant "extrêmement stressé )',
#         "Ressentez-vous de la fatigue mentale au travail ?",
#         "Comment percevez-vous votre charge de travail actuelle ? Est-elle agréable, trop importante ou insuffisante ?",
#         "Comment évaluez-vous la qualité de votre sommeil ?",
#         "Globalement, êtes-vous satisfait(e) de votre travail ?",
#         "Vous sentez-vous reconnu(e) pour votre travail ?",
#         "Êtes-vous motivé(e) au quotidien dans votre travail ?",
#         "Avez-vous des difficultés à vous concentrer au travail ?",
#         "Avez-vous des suggestions pour améliorer votre environnement de travail ?",
#     ]

#     # ✅ construire la ligne dans le bon ordre
#     row = [
#         payload.get("stress_level", ""),
#         payload.get("mental_fatigue", ""),
#         payload.get("workload", ""),
#         payload.get("sleep_quality", ""),
#         payload.get("job_satisfaction", ""),
#         payload.get("recognition", ""),
#         payload.get("motivation", ""),
#         payload.get("concentration_difficulty", ""),
#         payload.get("suggestions", ""),
#     ]

#     # ✅ si le fichier n'existe pas, on crée avec header
#     file_exists = os.path.exists(csv_path)

#     try:
#         os.makedirs(os.path.dirname(csv_path), exist_ok=True)
#         with open(csv_path, "a", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             if not file_exists:
#                 writer.writerow(headers)
#             writer.writerow(row)
#     except Exception as e:
#         return JsonResponse({"message": f"Error writing CSV: {str(e)}"}, status=500)

#     return JsonResponse({"message": "Réponse enregistrée ✅"})

FIELD_TO_QUESTION_TEXT = {
    "stress_level": 'Quel est votre niveau de stress au travail ?(1 étant "pas du tout stressé" , 5 étant "extrêmement stressé )',
    "mental_fatigue": "Ressentez-vous de la fatigue mentale au travail ?",
    "workload": "Comment percevez-vous votre charge de travail actuelle ? Est-elle agréable, trop importante ou insuffisante ?",
    "sleep_quality": "Comment évaluez-vous la qualité de votre sommeil ?",
    "job_satisfaction": "Globalement, êtes-vous satisfait(e) de votre travail ?",
    "recognition": "Vous sentez-vous reconnu(e) pour votre travail ?",
    "motivation": "Êtes-vous motivé(e) au quotidien dans votre travail ?",
    "concentration_difficulty": "Avez-vous des difficultés à vous concentrer au travail ?",
    "suggestions": "Avez-vous des suggestions pour améliorer votre environnement de travail ?",
}
@csrf_exempt
def get_active_survey(request):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    survey = Survey.objects.filter(is_active=True).order_by("-created_at").first()

    if not survey:
        return JsonResponse({"message": "Aucun survey actif."}, status=404)

    return JsonResponse({
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
    })

KEYS = [
    "stress_level",
    "mental_fatigue",
    "workload",
    "sleep_quality",
    "job_satisfaction",
    "recognition",
    "motivation",
    "concentration_difficulty",
    "suggestions",
]




@csrf_exempt
def save_survey_response(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    # 1) JSON
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    employee_id = payload.get("employee_id")
    survey_id = payload.get("survey_id")
    if not employee_id or not survey_id:
        return JsonResponse({"message": "employee_id et survey_id sont obligatoires"}, status=400)

    # 2) Validate FK
    employee = Employee.objects.filter(id=employee_id).first()
    survey = Survey.objects.filter(id=survey_id).first()
    if not employee or not survey:
        return JsonResponse({"message": "Employee ou Survey introuvable"}, status=404)

    # 3) Write DB atomically
    with transaction.atomic():
        response, created = SurveyResponse.objects.update_or_create(
            employee=employee,
            survey=survey,
            defaults={"submitted_at": timezone.now()},
        )

        for key in KEYS:
            q = Question.objects.filter(survey=survey, key=key).first()
            if not q:
                continue

            val = payload.get(key, "")
            if val is None:
                val = ""

            Answer.objects.update_or_create(
                response=response,
                question=q,
                defaults={"value": str(val)},
            )

    # 4) NLP incrémental (tu avais déjà)
    def _run_nlp(resp_id: int):
        try:
            update_nlp_state_for_response(resp_id)
        except Exception as e:
            print("NLP update error:", e)

    threading.Thread(target=_run_nlp, args=(response.id,), daemon=True).start()
    
    # 5) Risk cache (tu avais déjà)
    def _run_risk(resp_id):
        try:
            update_risk_cache_for_response(resp_id)
        except Exception as e:
            print("Risk cache error:", e)
    threading.Thread(target=_run_risk, args=(response.id,), daemon=True).start()

    # ────────────────────────────────────────────────
    # NOUVEAU : Lancement du questionnaire suivant (adaptatif)
    # ────────────────────────────────────────────────
    def _generate_next_questionnaire(resp_id: int):
        try:
            # Import ici pour éviter circular import
            from surveys.analytics.adaptive_questionnaire import generate_next_questionnaire
            
            next_q = generate_next_questionnaire(
                employee_id=employee_id,
                survey_id=survey_id
            )
            
            if next_q and not next_q.get("error"):
                print(f"Questionnaire de suivi round {next_q.get('round')} généré pour employé {employee_id}")
                # Optionnel : envoyer email ou stocker pour notification push
            else:
                print("Erreur génération questionnaire :", next_q)
        except Exception as e:
            print("Erreur génération questionnaire adaptatif :", str(e))

    threading.Thread(
        target=_generate_next_questionnaire,
        args=(response.id,),
        daemon=True
    ).start()

    # 6) Réponse rapide au frontend
    return JsonResponse({
        "message": "Réponse enregistrée ✅" if created else "Réponse mise à jour ✅",
        "updated": (not created),
        "analytics_async": True,
        "followup_generation_started": True   # ← optionnel, pour info frontend
    }, status=200)


@csrf_exempt
def my_survey_response(request):
    """
    GET /api/my-survey-response/?employee_id=8&survey_id=1
    Retourne {"exists": false} si aucune réponse
    """
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    employee_id = request.GET.get("employee_id")
    survey_id = request.GET.get("survey_id")

    if not employee_id or not survey_id:
        return JsonResponse({"message": "employee_id et survey_id requis"}, status=400)

    sr = SurveyResponse.objects.filter(employee_id=employee_id, survey_id=survey_id).first()
    if not sr:
        # ✅ IMPORTANT : 200 OK, pas une erreur
        return JsonResponse({"exists": False})

    answers = Answer.objects.filter(response=sr).select_related("question")

    data = {}
    for a in answers:
        data[a.question.key] = a.value if a.value is not None else ""

    return JsonResponse({
        "exists": True,
        "response_id": sr.id,
        "submitted_at": sr.submitted_at,
        "answers": data
    })

import os, json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count

from .models import SurveyResponse, Answer, Question

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# chemin exact chez toi:
LLM_SUMMARY_PATH = os.path.join(BASE_DIR, "analytics", "outputs", "llm_summary.json")


def _load_llm_summary():
    """
    Lit llm_summary.json s'il existe.
    """
    if not os.path.exists(LLM_SUMMARY_PATH):
        return None
    with open(LLM_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_db_global_stats():
    """
    Calcule n_rows + risk_distribution depuis la BD.
    Ici on compte le nombre total de SurveyResponse (une réponse = un questionnaire soumis).
    Pour risk_distribution, si tu ne stockes pas encore risk_level en BD,
    on renvoie seulement n_rows pour le moment.
    """
    n_rows = SurveyResponse.objects.count()

    # Si tu veux risk_distribution depuis BD, il faut stocker risk_level dans SurveyResponse
    # (ou recalculer à chaque requête: plus lourd).
    return {
        "n_rows": n_rows,
    }


@csrf_exempt
def analytics_summary(request):
    """
    GET /api/analytics/summary/
    Renvoie:
      - global depuis BD (n_rows_db + risk stats)
      - topics depuis llm_summary.json (clusters/keywords/examples)
    """
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    llm = _load_llm_summary()
    db_global = _compute_db_global_stats()

    # ✅ Charger risk stats depuis cache (rapide)
    risk_cache = load_risk_cache()
    if not risk_cache.get("per_response"):
        # cache absent => build 1 seule fois
        risk_cache = rebuild_risk_cache_full()

    risk_global = risk_cache.get("global", {})
    risk_distribution = risk_global.get("risk_distribution", {})
    avg_norm = risk_global.get("avg_risk_score_normalized", None)
    burnout_distribution = risk_global.get("burnout_distribution", {})
    avg_burnout = risk_global.get("avg_burnout_normalized", None)
    avg_productivity = risk_global.get("avg_productivity_impact", None)
    avg_discomfort = risk_global.get("avg_job_discomfort", None)
    # Cas où llm_summary.json n'existe pas encore
    if not llm:
        return JsonResponse({
            "message": "Résumé introuvable. Lance baseline_nlp.py pour générer llm_summary.json.",
            "global": {
                "n_rows_db": db_global["n_rows"],
                "risk_distribution": risk_distribution,
                "avg_risk_score_normalized": avg_norm,
            },
            "topics": [],
            "topic_examples": {}
        }, status=200)

    # Fusion: global llm_summary + global BD + risk cache
    global_out = llm.get("global", {})
    global_out["n_rows_db"] = db_global["n_rows"]

    # ✅ AJOUT IMPORTANT (fix dashboard)
    global_out["risk_distribution"] = risk_distribution
    global_out["avg_risk_score_normalized"] = avg_norm
    global_out["burnout_distribution"] = burnout_distribution
    global_out["avg_burnout_normalized"] = avg_burnout
    global_out["avg_productivity_impact"] = avg_productivity
    global_out["avg_job_discomfort"] = avg_discomfort
    return JsonResponse({
        "global": global_out,
        "topics": llm.get("topics", []),
        "topic_examples": llm.get("topic_examples", {})
    }, status=200)



@csrf_exempt
def my_analytics_summary(request):
    """
    GET /api/analytics/my-summary/?employee_id=1&survey_id=2
    Renvoie les analytics PERSONNELS de l’employé (sur sa dernière réponse au survey).
    """
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    employee_id = request.GET.get("employee_id")
    survey_id = request.GET.get("survey_id")

    if not employee_id or not survey_id:
        return JsonResponse({"message": "employee_id et survey_id sont obligatoires"}, status=400)

    employee = Employee.objects.filter(id=employee_id).first()
    survey = Survey.objects.filter(id=survey_id).first()
    if not employee or not survey:
        return JsonResponse({"message": "Employee ou Survey introuvable"}, status=404)

    # dernière réponse de cet employé à ce survey
    r = (
        SurveyResponse.objects
        .filter(employee=employee, survey=survey)
        .order_by("-submitted_at")
        .first()
    )

    if not r:
        return JsonResponse({
            "message": "Aucune réponse trouvée pour cet employé.",
            "global": {
                "employee_id": int(employee_id),
                "survey_id": int(survey_id),
                "response_id": None,
                "submitted_at": None,
                "risk_score_normalized": None,
                "risk_level": "UNKNOWN",
                "burnout_normalized": None,
                "burnout_level": "UNKNOWN",
                "productivity_impact_normalized": None,
                "job_discomfort_normalized": None,
            },
            "topics": [],
            "topic_examples": {}
        }, status=200)

    # charger cache
    risk_cache = load_risk_cache()
    if not risk_cache.get("per_response"):
        risk_cache = rebuild_risk_cache_full()

    # si pas trouvé dans cache -> update incremental
    per = (risk_cache.get("per_response") or {}).get(str(r.id))
    if not per:
        update_risk_cache_for_response(r.id)
        risk_cache = load_risk_cache()
        per = (risk_cache.get("per_response") or {}).get(str(r.id), {}) or {}

    return JsonResponse({
        "global": {
            "employee_id": int(employee_id),
            "survey_id": int(survey_id),
            "response_id": r.id,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,

            # ✅ RISQUE
            "risk_score_normalized": per.get("risk_score_normalized"),
            "risk_level": per.get("risk_level", "UNKNOWN"),

            # ✅ BURNOUT (cache: burnout_normalized)
            "burnout_normalized": per.get("burnout_normalized"),
            "burnout_level": per.get("burnout_level", "UNKNOWN"),

            # ✅ PRODUCTIVITE (cache: productivity_impact_normalized)
            "productivity_impact_normalized": per.get("productivity_impact_normalized"),

            # ✅ INCONFORT (cache: job_discomfort_normalized)
            "job_discomfort_normalized": per.get("job_discomfort_normalized"),
        },
        "topics": [],
        "topic_examples": {}
    }, status=200)

@csrf_exempt
def get_followup_questionnaire(request):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    employee_id = request.GET.get("employee_id")
    survey_id = request.GET.get("survey_id")

    if not employee_id or not survey_id:
        return JsonResponse({"message": "employee_id et survey_id requis"}, status=400)

    conv = EmployeeConversation.objects.filter(
        employee_id=employee_id,
        survey_id=survey_id
    ).order_by("-round_number").first()

    if not conv or conv.round_number == 1:
        return JsonResponse({"has_followup": False})

    last_round = conv.history["rounds"][-1]
    
    return JsonResponse({
        "has_followup": True,
        "round": last_round["round"],
        "introduction": last_round.get("introduction", ""),
        "questions": last_round.get("questions", []),
        "is_final_report": last_round.get("is_final_report", False)
    })
@csrf_exempt
def save_followup_response(request):
    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"message": "Invalid JSON"}, status=400)

    employee_id = payload.get("employee_id")
    survey_id = payload.get("survey_id")
    round_num = payload.get("round")
    responses = payload.get("responses", {})

    if not all([employee_id, survey_id, round_num]):
        return JsonResponse({"message": "Champs obligatoires manquants"}, status=400)

    conv = EmployeeConversation.objects.filter(
        employee_id=employee_id,
        survey_id=survey_id,
        round_number=round_num
    ).first()

    if not conv:
        return JsonResponse({"message": "Conversation de suivi introuvable"}, status=404)

    # Sauvegarde les réponses dans l'historique
    conv.history.setdefault("user_responses", {})[str(round_num)] = responses
    conv.save()

    return JsonResponse({
        "message": "Réponses au suivi enregistrées avec succès",
        "saved": True
    }, status=200)
@csrf_exempt
def get_employee_profile(request):
    """
    GET /api/employee-profile/?employee_id=X
    Retourne les infos de profil de l'employé
    """
    if request.method != "GET":
        return JsonResponse({"message": "Méthode non autorisée"}, status=405)

    employee_id = request.GET.get("employee_id")
    
    if not employee_id:
        return JsonResponse({"message": "employee_id requis"}, status=400)

    try:
        employee = Employee.objects.get(id=employee_id)
        
        return JsonResponse({
            "profile_completed": employee.is_profile_completed,
            "department": employee.department or "",
            "role": employee.role or "",
            "seniority": employee.seniority or "",
            "work_mode": employee.work_mode or "",
        })
    except Employee.DoesNotExist:
        return JsonResponse({"message": "Employé non trouvé"}, status=404)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)
# Dans surveys/views.py


# surveys/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.core.files.storage import default_storage
import os
import json

from .models import VoiceAnalysis
from .voice_utils import VoiceProcessor


# Dans surveys/views.py

class VoiceAnalysisView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        print("\n🔥 [DJANGO] Requête d'analyse vocale reçue")

        employee_id = request.data.get('employee_id', 1)

        audio_files = sorted([
            (k, f) for k, f in request.FILES.items()
            if k.startswith('audio_')
        ])

        if not audio_files:
            return Response(
                {'error': 'Aucun fichier audio reçu'},
                status=status.HTTP_400_BAD_REQUEST
            )

        print(f"📱 Nombre de réponses : {len(audio_files)}")

        processor = VoiceProcessor()
        all_transcripts = []
        temp_paths = []

        try:
            # 1. Sauvegarde de tous les fichiers
            for key, file in audio_files:
                path = default_storage.save(f'temp/{file.name}', file)
                temp_path = default_storage.path(path)
                temp_paths.append(temp_path)

            # 2. Transcription de chaque fichier
            for i, temp_path in enumerate(temp_paths):
                text = processor.transcribe(temp_path)
                all_transcripts.append(f"Q{i+1}: {text}")

            full_transcript = " ".join(all_transcripts)

            # ══════════════════════════════════════════════════════
            # ✅ CHANGEMENT ICI : Passer TOUS les audios + texte
            # ══════════════════════════════════════════════════════
            emotion = processor.detect_emotion(
                audio_paths=temp_paths,           # ← Liste des 5 audios
                full_transcript=full_transcript   # ← Texte complet
            )

            skills = processor.extract_skills(full_transcript)
            recommendation = processor.get_position_recommendation(skills)

            first_rec = recommendation['recommendations'][0] if recommendation['recommendations'] else {}

            analysis = VoiceAnalysis.objects.create(
                employee_id=employee_id,
                transcript=full_transcript,
                emotion=emotion['emotion'],
                emotion_confidence=emotion['confidence'],
                current_skills=skills['current_skills'],
                desired_skills=skills['desired_skills'],
                recommended_position=first_rec.get('position', 'Aucune'),
                match_score=first_rec.get('score', 0),
                all_recommendations=recommendation['recommendations'],
                validated_positions=[]
            )

            print(f"💾 Analyse sauvegardée ID: {analysis.id}")

            return Response({
                "id": analysis.id,
                "transcript": full_transcript,
                "emotion": emotion,
                "skills": skills,
                "recommendation": recommendation
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ ERREUR: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)

class ValidatePositionsView(APIView):
    """
    Endpoint pour valider les postes recommandés par l'employé
    POST /api/voice/validate-positions/
    Body: { "analysis_id": 1, "validated_positions": ["Data Scientist Senior"] }
    """

    def post(self, request):
        analysis_id = request.data.get('analysis_id')
        validated_positions = request.data.get('validated_positions', [])

        if not analysis_id:
            return Response(
                {'error': 'analysis_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            analysis = VoiceAnalysis.objects.get(id=analysis_id)
            analysis.validated_positions = validated_positions
            analysis.is_sent_to_hr = len(validated_positions) > 0
            analysis.save()

            print(f"✅ Postes validés pour analyse {analysis_id}: {validated_positions}")

            return Response({
                'success': True,
                'message': 'Vos choix ont été envoyés aux RH' if validated_positions else 'Aucun poste sélectionné',
                'validated_positions': validated_positions,
                'analysis_id': analysis_id
            }, status=status.HTTP_200_OK)

        except VoiceAnalysis.DoesNotExist:
            return Response(
                {'error': 'Analyse non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VoiceAnalysisListView(APIView):
    """Endpoint pour l'admin : récupère toutes les analyses vocales"""

    def get(self, request):
        analyses = VoiceAnalysis.objects.all().order_by('-created_at')

        data = [{
            'id': a.id,
            'employee_id': a.employee_id,
            'transcript': a.transcript,
            'emotion': a.emotion,
            'emotion_confidence': a.emotion_confidence,
            'current_skills': a.current_skills,
            'desired_skills': a.desired_skills,
            'recommended_position': a.recommended_position,
            'match_score': a.match_score,
            'all_recommendations': getattr(a, 'all_recommendations', []),
            'validated_positions': getattr(a, 'validated_positions', []),
            'is_sent_to_hr': getattr(a, 'is_sent_to_hr', False),
            'created_at': a.created_at,
        } for a in analyses]

        return Response({'analyses': data})