from .medical_rules import detect_symptoms
from .llm_service import generate_medical_text

def build_full_report(metrics):
    posture_time = metrics.get("posture_time", {})
    total_time = metrics.get("total_time", 0)
    
    # Récupération de la fatigue visuelle
    fatigue_data = metrics.get("fatigue_visuelle_data", {
        "perclos": 0, "blink_rate": 0, "microsleeps": 0, "fatigue_score": 0
    })

    # 🔥 calcul temps mauvaise posture
    bad_time = sum(posture_time.values())
    bad_pct = (bad_time / total_time * 100) if total_time > 0 else 0

    # 🔥 symptômes + conditions (inclut désormais la vision)
    symptoms, conditions = detect_symptoms(metrics)

    # 🔥 LLM (texte médical enrichi par Gemini)
    llm_text = generate_medical_text(metrics, symptoms, conditions)

    # 🔥 détail par posture
    details = {}
    for key, val in posture_time.items():
        pct = (val / total_time * 100) if total_time > 0 else 0
        details[key] = {
            "time_sec": round(val, 1),
            "percent": round(pct, 1)
        }

    return {
        "score_posture": metrics.get("score", 0),
        "bad_posture_pct": round(bad_pct, 1),
        "total_time": round(total_time, 1),

        "mauvaise_posture": details,
        # Injection propre des données de fatigue visuelle
        "fatigue_visuelle": fatigue_data,

        "symptoms": symptoms,
        "conditions": conditions,

        "llm_report": llm_text,

        "warning": "⚠️ Ce diagnostic est une estimation basée sur l’analyse biométrique (posture et flux oculaire) et ne remplace pas un avis médical professionnel."
    }