# surveys/analytics/risk_cache.py
import os, json
import pandas as pd
from collections import defaultdict

from surveys.models import SurveyResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

RISK_CACHE_PATH = os.path.join(OUT_DIR, "risk_cache.json")

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

# --- mêmes maps que ton baseline_nlp.py ---
FATIGUE_MAP = {"Jamais": 0, "Rarement": 1, "Parfois": 2, "Souvent": 3, "Très souvent": 4}
SLEEP_MAP   = {"Très mauvaise": 0, "Mauvaise": 1, "Moyenne": 2, "Bonne": 3, "Très bonne": 4}
SAT_MAP     = {"Très insatisfait(e)": 0, "Insatisfait(e)": 1, "Neutre": 2, "Satisfait(e)": 3, "Très satisfait(e)": 4}
YES_MAP     = {"Pas du tout": 0, "Peu": 1, "Moyennement": 2, "Oui": 3, "Oui, totalement": 4}
CONC_MAP    = {"Jamais": 0, "Parfois": 1, "Souvent": 2, "Très souvent": 3}
WORKLOAD_MAP= {"Insuffisante": -1, "Agréable": 0, "Trop importante": 1}

MIN_SCORE = -8.0
MAX_SCORE = 29.5

# Burnout score: on peut aussi normaliser sur 0..100 plus tard
BURNOUT_HIGH = 15
BURNOUT_MED  = 8

def _risk_level(score):
    if score is None:
        return "UNKNOWN"
    if score >= 12:
        return "HIGH"
    if score >= 7:
        return "MEDIUM"
    return "LOW"

def compute_risk_for_answers(ans: dict):
    """
    ans: dict avec clés KEYS -> valeur string
    Retourne: risk + burnout + productivity + discomfort
    """
    try:
        stress = int(ans.get("stress_level") or 0)
    except:
        stress = None

    fatigue = FATIGUE_MAP.get(ans.get("mental_fatigue"), None)
    sleep   = SLEEP_MAP.get(ans.get("sleep_quality"), None)
    sat     = SAT_MAP.get(ans.get("job_satisfaction"), None)
    rec     = YES_MAP.get(ans.get("recognition"), None)
    mot     = YES_MAP.get(ans.get("motivation"), None)
    conc    = CONC_MAP.get(ans.get("concentration_difficulty"), None)
    wl      = WORKLOAD_MAP.get(ans.get("workload"), None)

    nums = [stress, fatigue, sleep, sat, rec, mot, conc, wl]
    if any(v is None for v in nums):
        return {
            "risk_score": None,
            "risk_score_normalized": None,
            "risk_level": "UNKNOWN",

            "burnout_score": None,
            "burnout_level": "UNKNOWN",

            "productivity_impact_score": None,
            "productivity_impact_normalized": None,

            "job_discomfort_score": None,
            "job_discomfort_normalized": None,
        }

    # --------------------------
    # 1) Risk (déjà chez toi)
    # --------------------------
    risk_score = (
        stress * 2
        + fatigue * 2
        + (4 - sleep) * 1.5
        + conc * 1.5
        + max(wl, 0) * 1.0
        - sat * 1.0
        - mot * 0.5
        - rec * 0.5
    )
    risk_norm = ((risk_score - MIN_SCORE) / (MAX_SCORE - MIN_SCORE)) * 100
    risk_norm = max(0.0, min(100.0, float(risk_norm)))

    # --------------------------
    # 2) Burnout Index (interprétable)
    # --------------------------
    burnout_score = (
        stress * 2
        + fatigue * 2
        + (4 - sleep) * 1.5
        + conc * 1.5
        - mot * 1.0
    )
    burnout_level = _burnout_level(burnout_score)

    # Normalisation simple (bornes choisies “raisonnables”)
    # approx min=0, max= (stress=5*2=10)+(fatigue=4*2=8)+(sleep=0=>6)+(conc=3=>4.5)-(mot=4)=> -4 => total max ~20.5
    burnout_norm = _norm_0_100(burnout_score, 0.0, 21.0)

    # --------------------------
    # 3) Productivity Impact
    # --------------------------
    productivity_impact = (
        conc * 2.0
        + fatigue * 1.5
        + stress * 1.0
        - mot * 1.0
        - sat * 1.0
    )
    # bornes approx: min ~ -8 ; max ~ 20
    productivity_norm = _norm_0_100(productivity_impact, -8.0, 20.0)

    # --------------------------
    # 4) Job Discomfort
    # --------------------------
    job_discomfort = (
        (4 - sat) * 1.0
        + (4 - rec) * 1.0
        + max(wl, 0) * 1.0
    )
    # bornes approx: min=0 max=(4+4+1)=9
    job_discomfort_norm = _norm_0_100(job_discomfort, 0.0, 9.0)

    return {
        "risk_score": float(risk_score),
        "risk_score_normalized": float(risk_norm),
        "risk_level": _risk_level(risk_score),

        "burnout_score": float(burnout_score),
        "burnout_level": burnout_level,
        "burnout_normalized": burnout_norm,

        "productivity_impact_score": float(productivity_impact),
        "productivity_impact_normalized": productivity_norm,

        "job_discomfort_score": float(job_discomfort),
        "job_discomfort_normalized": job_discomfort_norm,
    }

def load_risk_cache():
    if not os.path.exists(RISK_CACHE_PATH):
        return {"per_response": {}, "global": {}}
    with open(RISK_CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_risk_cache(cache):
    with open(RISK_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def rebuild_risk_cache_full():
    """
    À lancer une fois si cache absent.
    """
    qs = SurveyResponse.objects.prefetch_related("answers__question").all()

    per = {}
    for r in qs:
        ans = {k: "" for k in KEYS}
        for a in r.answers.all():
            if a.question and a.question.key in ans:
                ans[a.question.key] = a.value or ""
        per[str(r.id)] = compute_risk_for_answers(ans)

    cache = {"per_response": per}
    cache["global"] = compute_global_from_per(per)
    save_risk_cache(cache)
    return cache
def compute_global_from_per(per: dict):
    dist_risk = defaultdict(int)
    dist_burnout = defaultdict(int)

    risk_scores = []
    burnout_scores = []
    prod_scores = []
    discomfort_scores = []

    for v in per.values():
        # risk
        lvl = v.get("risk_level", "UNKNOWN")
        dist_risk[lvl] += 1
        if v.get("risk_score_normalized") is not None:
            risk_scores.append(float(v["risk_score_normalized"]))

        # burnout
        blvl = v.get("burnout_level", "UNKNOWN")
        dist_burnout[blvl] += 1
        if v.get("burnout_normalized") is not None:
            burnout_scores.append(float(v["burnout_normalized"]))

        # productivity
        if v.get("productivity_impact_normalized") is not None:
            prod_scores.append(float(v["productivity_impact_normalized"]))

        # discomfort
        if v.get("job_discomfort_normalized") is not None:
            discomfort_scores.append(float(v["job_discomfort_normalized"]))

    def _avg(arr):
        return (sum(arr) / len(arr)) if arr else None

    return {
        # existing
        "risk_distribution": dict(dist_risk),
        "avg_risk_score_normalized": _avg(risk_scores),

        # new
        "burnout_distribution": dict(dist_burnout),
        "avg_burnout_normalized": _avg(burnout_scores),
        "avg_productivity_impact": _avg(prod_scores),
        "avg_job_discomfort": _avg(discomfort_scores),
    }


def update_risk_cache_for_response(response_id: int):
    """
    Mise à jour incrémentale : 1 seule réponse.
    """
    cache = load_risk_cache()

    r = SurveyResponse.objects.prefetch_related("answers__question").filter(id=response_id).first()
    if not r:
        return cache

    ans = {k: "" for k in KEYS}
    for a in r.answers.all():
        if a.question and a.question.key in ans:
            ans[a.question.key] = a.value or ""

    cache["per_response"][str(response_id)] = compute_risk_for_answers(ans)
    cache["global"] = compute_global_from_per(cache["per_response"])
    save_risk_cache(cache)
    return cache

def _burnout_level(score):
    if score is None:
        return "UNKNOWN"
    if score >= BURNOUT_HIGH:
        return "HIGH"
    if score >= BURNOUT_MED:
        return "MEDIUM"
    return "LOW"

def _norm_0_100(x, min_x, max_x):
    if x is None:
        return None
    if max_x == min_x:
        return 0.0
    v = ((x - min_x) / (max_x - min_x)) * 100.0
    return float(max(0.0, min(100.0, v)))
