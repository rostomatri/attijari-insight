# surveys/analytics/builder.py
import os, json
import pandas as pd
from django.conf import settings
from surveys.models import SurveyResponse, Answer

# ✅ importe tes fonctions depuis baseline_nlp.py (mets baseline_nlp.py au bon endroit / module)
from surveys.analytics.baseline_nlp import add_risk_score, run_nlp_analysis, build_llm_summary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

DF_BASELINE_PATH = os.path.join(OUT_DIR, "df_baseline.csv")
LLM_SUMMARY_PATH = os.path.join(OUT_DIR, "llm_summary.json")
NLP_RESULT_PATH = os.path.join(OUT_DIR, "nlp_result.json")


REQUIRED_KEYS = [
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


def _responses_to_df() -> pd.DataFrame:
    """
    Convertit les SurveyResponse + Answer en DataFrame
    Colonnes = Question.key
    """
    rows = []
    qs = (
        SurveyResponse.objects
        .select_related("employee", "survey")
        .prefetch_related("answers__question")
        .all()
        .order_by("submitted_at")
    )

    for r in qs:
        row = {"response_id": r.id, "employee_id": r.employee_id, "survey_id": r.survey_id, "submitted_at": r.submitted_at}
        for a in r.answers.all():
            if a.question_id and a.question and a.question.key:
                row[a.question.key] = a.value
        rows.append(row)

    df = pd.DataFrame(rows)

    # assurer toutes les colonnes nécessaires
    for k in REQUIRED_KEYS:
        if k not in df.columns:
            df[k] = None

    return df


def rebuild_analytics_snapshot():
    """
    Rebuild complet:
    - extrait BD -> df
    - calcule risk score
    - NLP topics
    - écrit df_baseline.csv + llm_summary.json (+ nlp_result.json optionnel)
    """
    df = _responses_to_df()

    # risk baseline
    df_scored = add_risk_score(df)

    # NLP topics (sur suggestions)
    nlp_result = run_nlp_analysis(df_scored)

    # summary
    llm_summary = build_llm_summary(df_scored, nlp_result)

    # write outputs
    df_scored.to_csv(DF_BASELINE_PATH, index=False, encoding="utf-8")

    with open(NLP_RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(nlp_result, f, ensure_ascii=False, indent=2)

    with open(LLM_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(llm_summary, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "n_rows": int(len(df_scored)),
        "df_path": DF_BASELINE_PATH,
        "llm_summary_path": LLM_SUMMARY_PATH,
        "nlp_result_path": NLP_RESULT_PATH,
        "nlp_ok": bool(nlp_result.get("ok")),
    }