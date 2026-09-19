# surveys/analytics/trigger.py
import os, json, threading
from surveys.models import SurveyResponse
from surveys.analytics.builder import rebuild_analytics_snapshot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

LLM_SUMMARY_PATH = os.path.join(OUT_DIR, "llm_summary.json")

_lock = threading.Lock()
_running = False


def _load_last_id():
    if not os.path.exists(LLM_SUMMARY_PATH):
        return 0
    try:
        with open(LLM_SUMMARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("meta", {}).get("last_response_id", 0))
    except Exception:
        return 0


def _save_last_id(last_id: int):
    if not os.path.exists(LLM_SUMMARY_PATH):
        return
    try:
        with open(LLM_SUMMARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["meta"] = data.get("meta", {})
        data["meta"]["last_response_id"] = int(last_id)
        with open(LLM_SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _background_rebuild():
    global _running
    try:
        rebuild_analytics_snapshot()
        newest = SurveyResponse.objects.order_by("-id").values_list("id", flat=True).first() or 0
        _save_last_id(newest)
    finally:
        with _lock:
            _running = False


def trigger_rebuild_if_needed(min_new: int = 20):
    """
    Lance rebuild en background seulement si min_new nouvelles réponses depuis dernier rebuild.
    """
    global _running

    last_done = _load_last_id()
    newest = SurveyResponse.objects.order_by("-id").values_list("id", flat=True).first() or 0
    new_count = max(0, newest - last_done)

    if new_count < min_new:
        return  # rien à faire

    with _lock:
        if _running:
            return
        _running = True

    t = threading.Thread(target=_background_rebuild, daemon=True)
    t.start()