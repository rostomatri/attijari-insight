# surveys/analytics/adaptive_questionnaire.py

import os
import json
from openai import OpenAI
from django.conf import settings
from django.utils import timezone
from .builder import rebuild_analytics_snapshot
from ..models import EmployeeConversation, SurveyResponse, Answer
import os
from dotenv import load_dotenv

load_dotenv()  # charge .env
# ────────────────────────────────────────────────
# CONFIGURATION GITHUB MODELS (gratuit – tier limité)
# ────────────────────────────────────────────────

# IMPORTANT : mets ton Personal Access Token GitHub dans .env ou settings.py
# GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

client = OpenAI(
    base_url="https://models.github.ai/inference",           # endpoint officiel GitHub Models
    api_key=os.getenv("GITHUB_TOKEN") or getattr(settings, "GITHUB_TOKEN", None),
)

# Choisis l'un des deux (grok-3-mini est souvent plus permissif en free tier)
#MODEL_NAME = "azureml-xai/grok-3-mini"          # ← recommandé pour débuter (moins limité)
MODEL_NAME = "xai/grok-3"             # plus puissant mais limites encore plus basses

SYSTEM_PROMPT = """
Tu es un expert RH et coach bien-être en entreprise. 
Tu génères des questionnaires de suivi ultra-personnalisés.
Tu gardes toujours un ton bienveillant, professionnel et encourageant.
Tu ne poses jamais les mêmes questions deux fois.
Tu t'appuies sur l'historique complet pour creuser plus profond.
"""

def get_or_create_conversation(employee_id, survey_id):
    # Trouve la conversation la plus récente (dernier round)
    latest_conv = EmployeeConversation.objects.filter(
        employee_id=employee_id,
        survey_id=survey_id
    ).order_by('-round_number').first()

    if latest_conv:
        # On veut créer le round SUIVANT
        next_round = latest_conv.round_number + 1
        conv, created = EmployeeConversation.objects.get_or_create(
            employee_id=employee_id,
            survey_id=survey_id,
            round_number=next_round,
            defaults={"history": {"rounds": latest_conv.history.get("rounds", [])}}
        )
        return conv
    else:
        # Première fois → round 1
        conv, created = EmployeeConversation.objects.get_or_create(
            employee_id=employee_id,
            survey_id=survey_id,
            round_number=1,
            defaults={"history": {"rounds": []}}
        )
        return conv


def build_full_history(conv: EmployeeConversation, last_answers: dict, last_analysis: dict):
    """ Construit le contexte complet pour le LLM """
    history = conv.history.get("rounds", [])
    
    current_round = {
        "round": conv.round_number,
        "submitted_at": last_response.submitted_at.isoformat() if 'last_response' in globals() else None,
        "questionnaire": last_answers,
        "analysis": last_analysis,
    }
    history.append(current_round)
    
    return {
        "employee_id": conv.employee_id,
        "total_rounds": len(history),
        "max_rounds": 4,
        "history": history[-4:],                 # mémoire glissante (4 derniers rounds)
        "global_summary": _load_global_llm_summary()
    }


def _load_global_llm_summary():
    path = os.path.join(settings.BASE_DIR, "analytics", "outputs", "llm_summary.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def generate_next_questionnaire(employee_id: int, survey_id: int):
    conv = get_or_create_conversation(employee_id, survey_id)
    
    # Récupère la DERNIÈRE réponse soumise
    last_response = SurveyResponse.objects.filter(
        employee_id=employee_id,
        survey_id=survey_id
    ).order_by("-submitted_at").first()
    
    if not last_response:
        return {"error": "Aucune réponse trouvée pour cet employé et ce survey"}
    
    answers = {a.question.key: a.value for a in last_response.answers.all()}
    
    # Mise à jour incrémentale (tu avais déjà ces fonctions)
    from .incremental_nlp import update_nlp_state_for_response
    from .risk_cache import update_risk_cache_for_response
    
    update_nlp_state_for_response(last_response.id)
    update_risk_cache_for_response(last_response.id)
    
    # Récupère l'analyse réelle (à adapter selon ton implémentation actuelle)
    # Ici on met des valeurs d'exemple – remplace par ton vrai cache
    analysis = {
        "risk_score_normalized": 75.0,
        "risk_level": "MEDIUM",
        "burnout_normalized": 68.0,
        "burnout_level": "MODERATE",
        "topics": ["charge de travail", "manque de reconnaissance", "fatigue mentale"]
    }
    
    full_context = build_full_history(conv, answers, analysis)
    
    # ────────────────────────────────────────────────
    # PROMPT FINAL – très important de dire qu'on est limité
    # ────────────────────────────────────────────────
    prompt = f"""
Tu es Grok-3 (via GitHub Models – usage très limité).

Historique complet de l'employé (jusqu'au round {full_context['total_rounds']}) :

{json.dumps(full_context, ensure_ascii=False, indent=2)}

Règles strictes :
- Génère un questionnaire de SUIVI pour le round {full_context['total_rounds'] + 1}
- MAXIMUM 6–7 questions (pas plus)
- Chaque question doit faire référence explicite à une réponse ou un thème précédent
- Varie les formats : échelle 1-10, choix multiple, ouverte, priorisation
- Ton bienveillant, encourageant, professionnel
- Si total_rounds >= 4 → génère plutôt un court rapport final synthétique

Réponds UNIQUEMENT avec un JSON valide, sans texte avant/après :

{{
  "round": {full_context['total_rounds'] + 1},
  "introduction": "Bonjour , merci pour tes réponses récentes...",
  "questions": [
    {{"id": "q1", "text": "Question ici...", "type": "scale|open|multiple|rank"}},
    ...
  ],
  "is_final_report": false
}}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.65,
            max_tokens=1000,
            top_p=0.9
        )
        
        content = response.choices[0].message.content.strip()
        
        # GitHub Models renvoie parfois du markdown → nettoyage
        if content.startswith("```json"):
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content.split("```", 2)[1].strip()
        
        result = json.loads(content)
        
        # Mise à jour de la conversation
        conv.round_number += 1
        conv.history.setdefault("rounds", []).append(result)
        conv.save()
        
        return result

    except json.JSONDecodeError as e:
        return {"error": f"Réponse LLM non-JSON valide : {str(e)}\nContenu brut : {content}"}
    
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            return {"error": "Rate limit dépassé (limite GitHub Models free : ~15 req/jour)"}
        elif "401" in error_msg or "authentication" in error_msg.lower():
            return {"error": "Token GitHub invalide ou expiré – vérifie GITHUB_TOKEN"}
        else:
            return {"error": f"Erreur lors de l'appel GitHub Models : {error_msg}"}


# Optionnel : petite fonction de debug pour voir les limites
def get_remaining_calls_estimate():
    # Pas d'API pour ça → juste un rappel manuel
    return "Free tier GitHub Models : ~15 requêtes/jour max pour Grok-3"