# surveys/analytics/incremental_nlp.py
import os, json, re, math
from collections import defaultdict
import numpy as np
import joblib

from django.db.models import Prefetch
from surveys.models import SurveyResponse

from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans

# =========================
# Paths
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

STATE_PATH = os.path.join(OUT_DIR, "nlp_state.joblib")         # kmeans + meta
AGG_PATH   = os.path.join(OUT_DIR, "nlp_agg.json")            # counts/terms/examples + per_response map
LLM_PATH   = os.path.join(OUT_DIR, "llm_summary.json")        # dashboard reads this

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# =========================
# Caches (important performance)
# =========================
_EMBEDDER = None
_KMEANS = None

def get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(MODEL_NAME)
    return _EMBEDDER

def get_kmeans():
    global _KMEANS
    if _KMEANS is None and os.path.exists(STATE_PATH):
        blob = joblib.load(STATE_PATH)
        _KMEANS = blob["kmeans"]
    return _KMEANS

def save_kmeans(km, k: int):
    global _KMEANS
    _KMEANS = km
    joblib.dump({"kmeans": km, "model_name": MODEL_NAME, "k": int(k)}, STATE_PATH)

# =========================
# Text utils
# =========================
def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ\s'-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize(text: str):
    # simple tokens >= 3 chars
    toks = [t for t in re.split(r"\s+", text) if len(t) >= 3]
    return toks

def text_fingerprint(text: str) -> str:
    # hash simple stable (pas besoin crypto)
    return str(hash(text))

# =========================
# Load/save aggregator state
# =========================
def _empty_agg():
    return {
        "cluster_counts": {},          # "0": 123
        "cluster_terms": {},           # "0": {"charge": 50, ...}
        "cluster_examples": {},        # "0": ["...", "..."]
        "per_response": {},            # response_id(str) -> {"cluster": int, "tokens": {tok:count}, "fp": "...", "text": "..."}
        "meta": {"k": None}
    }

def load_agg():
    if not os.path.exists(AGG_PATH):
        return _empty_agg()
    with open(AGG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_agg(agg):
    with open(AGG_PATH, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)

# =========================
# Build llm_summary.json from agg
# =========================
def write_llm_summary_from_agg(agg):
    topics = []
    for c_str, cnt in agg.get("cluster_counts", {}).items():
        terms = agg.get("cluster_terms", {}).get(c_str, {})
        top_terms = sorted(terms.items(), key=lambda x: x[1], reverse=True)[:8]
        topics.append({
            "cluster": int(c_str),
            "keywords": [w for w, _ in top_terms],
            "count": int(cnt),
        })

    topics.sort(key=lambda x: x["count"], reverse=True)

    out = {
        "global": {
            "n_rows": int(sum(int(v) for v in agg.get("cluster_counts", {}).values())),
        },
        "topics": topics,
        "topic_examples": agg.get("cluster_examples", {}),
        "meta": {
            "k": agg.get("meta", {}).get("k"),
        }
    }
    with open(LLM_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

# =========================
# DB helpers
# =========================
def get_suggestion_text_for_response(r: SurveyResponse) -> str:
    sugg = ""
    for a in r.answers.all():
        if a.question and a.question.key == "suggestions":
            sugg = a.value or ""
            break
    return clean_text(sugg)

def fetch_all_suggestions():
    qs = (SurveyResponse.objects
          .prefetch_related("answers__question")
          .all()
          .order_by("id"))
    rows = []
    for r in qs:
        t = get_suggestion_text_for_response(r)
        if t.strip():
            rows.append((r.id, t))
    return rows

def fetch_one_response(response_id: int):
    return (SurveyResponse.objects
            .prefetch_related("answers__question")
            .filter(id=response_id)
            .first())

# =========================
# Choosing optimal K (Elbow detection)
# =========================
def _elbow_best_k(ks, inertias):
    """
    Pick elbow by max distance from line between first and last points.
    """
    x = np.array(ks, dtype=float)
    y = np.array(inertias, dtype=float)

    # line between endpoints
    x1, y1 = x[0], y[0]
    x2, y2 = x[-1], y[-1]

    # distance point -> line
    denom = math.sqrt((y2 - y1)**2 + (x2 - x1)**2) + 1e-9
    dists = []
    for xi, yi in zip(x, y):
        num = abs((y2 - y1)*xi - (x2 - x1)*yi + x2*y1 - y2*x1)
        dists.append(num / denom)

    best_idx = int(np.argmax(dists))
    return int(ks[best_idx])

def choose_k_elbow(embeddings: np.ndarray, k_min=2, k_max=12):
    ks = []
    inertias = []

    max_k = min(k_max, max(k_min, len(embeddings) - 1))
    for k in range(k_min, max_k + 1):
        km = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=256)
        km.fit(embeddings)
        ks.append(k)
        inertias.append(float(km.inertia_))

    if len(ks) < 2:
        return k_min

    return _elbow_best_k(ks, inertias)

# =========================
# INIT (run once)
# =========================
def init_incremental_nlp(k_min=2, k_max=12, sample_size=2000):
    """
    À lancer une seule fois après import 10k:
    - calcule embeddings (échantillon pour K)
    - choisit K (coude)
    - fit MiniBatchKMeans sur tous les textes
    - construit l'état agg + per_response
    """
    rows = fetch_all_suggestions()  # [(id, text), ...]
    if len(rows) < 10:
        raise RuntimeError("Pas assez de suggestions pour initialiser l'analyse NLP.")

    # embeddings pour choisir K (sample)
    embedder = get_embedder()
    sample = rows[:min(sample_size, len(rows))]
    sample_texts = [t for _, t in sample]
    E_sample = embedder.encode(sample_texts, normalize_embeddings=True, show_progress_bar=True)

    best_k = choose_k_elbow(E_sample, k_min=k_min, k_max=k_max)

    # fit sur TOUS les textes
    texts = [t for _, t in rows]
    ids = [rid for rid, _ in rows]
    E_all = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    km = MiniBatchKMeans(n_clusters=best_k, random_state=42, batch_size=256)
    km.fit(E_all)
    save_kmeans(km, best_k)

    labels = km.predict(E_all)

    agg = _empty_agg()
    agg["meta"]["k"] = int(best_k)

    # init structures
    cluster_counts = defaultdict(int)
    cluster_terms = defaultdict(lambda: defaultdict(int))
    cluster_examples = defaultdict(list)
    per_response = {}

    for rid, text, lab in zip(ids, texts, labels):
        c = str(int(lab))
        cluster_counts[c] += 1

        toks = tokenize(text)
        tok_counts = defaultdict(int)
        for tok in toks:
            cluster_terms[c][tok] += 1
            tok_counts[tok] += 1

        # examples (max 3)
        if len(cluster_examples[c]) < 3:
            cluster_examples[c].append(text)

        per_response[str(rid)] = {
            "cluster": int(lab),
            "tokens": dict(tok_counts),
            "fp": text_fingerprint(text),
            "text": text,
        }

    agg["cluster_counts"] = {k: int(v) for k, v in cluster_counts.items()}
    agg["cluster_terms"] = {k: dict(v) for k, v in cluster_terms.items()}
    agg["cluster_examples"] = {k: v for k, v in cluster_examples.items()}
    agg["per_response"] = per_response

    save_agg(agg)
    write_llm_summary_from_agg(agg)
    return {"ok": True, "k": int(best_k), "n_texts": int(len(rows))}

# =========================
# INCREMENTAL UPDATE (replace old analysis)
# =========================
def _remove_old_contrib(agg, rid_str: str):
    old = agg.get("per_response", {}).get(rid_str)
    if not old:
        return agg

    c = str(int(old["cluster"]))
    # counts
    if c in agg["cluster_counts"]:
        agg["cluster_counts"][c] = max(0, int(agg["cluster_counts"][c]) - 1)

    # terms
    old_tokens = old.get("tokens", {})
    terms = agg.get("cluster_terms", {}).get(c, {})
    for tok, cnt in old_tokens.items():
        if tok in terms:
            terms[tok] = int(terms[tok]) - int(cnt)
            if terms[tok] <= 0:
                del terms[tok]
    agg["cluster_terms"][c] = terms

    # examples: remove old text if present
    ex = agg.get("cluster_examples", {}).get(c, [])
    old_text = old.get("text", "")
    if old_text in ex:
        ex = [x for x in ex if x != old_text]
        agg["cluster_examples"][c] = ex

    # remove per_response entry (we will re-add)
    del agg["per_response"][rid_str]
    return agg

def _add_new_contrib(agg, rid_str: str, text: str, km, embedder):
    # embedding 1 texte
    x = embedder.encode([text], normalize_embeddings=True)
    lab = int(km.predict(x)[0])

    # (optionnel) incremental learning
    km.partial_fit(x)
    save_kmeans(km, agg["meta"]["k"])

    c = str(lab)

    agg["cluster_counts"][c] = int(agg["cluster_counts"].get(c, 0)) + 1

    # terms update
    terms = agg["cluster_terms"].get(c, {})
    tok_counts = defaultdict(int)
    for tok in tokenize(text):
        terms[tok] = int(terms.get(tok, 0)) + 1
        tok_counts[tok] += 1
    agg["cluster_terms"][c] = terms

    # examples: keep last 3 (recent)
    ex = agg["cluster_examples"].get(c, [])
    ex.append(text)
    if len(ex) > 3:
        ex = ex[-3:]
    agg["cluster_examples"][c] = ex

    # save per_response
    agg["per_response"][rid_str] = {
        "cluster": lab,
        "tokens": dict(tok_counts),
        "fp": text_fingerprint(text),
        "text": text,
    }

    return agg

def update_nlp_state_for_response(response_id: int):
    """
    Appelé à chaque création/modification de réponse.
    - retire l'ancienne contribution (si existante)
    - ajoute la nouvelle
    """
    # must be initialized first
    if not os.path.exists(STATE_PATH) or not os.path.exists(AGG_PATH):
        # fallback: init from all data (first time)
        init_incremental_nlp()

    agg = load_agg()
    km = get_kmeans()
    embedder = get_embedder()

    r = fetch_one_response(response_id)
    if not r:
        return {"ok": False, "message": "SurveyResponse introuvable"}

    text = get_suggestion_text_for_response(r)
    rid_str = str(response_id)

    # if empty -> remove old and stop
    if not text.strip():
        if rid_str in agg.get("per_response", {}):
            agg = _remove_old_contrib(agg, rid_str)
            save_agg(agg)
            write_llm_summary_from_agg(agg)
        return {"ok": True, "action": "removed_empty"}

    # if unchanged -> skip
    fp = text_fingerprint(text)
    old = agg.get("per_response", {}).get(rid_str)
    if old and old.get("fp") == fp:
        return {"ok": True, "action": "no_change"}

    # replace
    if old:
        agg = _remove_old_contrib(agg, rid_str)

    agg = _add_new_contrib(agg, rid_str, text, km, embedder)

    save_agg(agg)
    write_llm_summary_from_agg(agg)
    return {"ok": True, "action": "replaced"}