import os
import json
import re
import numpy as np
import pandas as pd
import cv2
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer

from sentence_transformers import SentenceTransformer
from transformers import pipeline
import mediapipe as mp
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
mp_pose = mp.solutions.pose

# ============================================================
# 1) CONFIG - chemins + colonnes
# ============================================================

BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "synthetic_data.csv")  # adapte ton chemin

# Mapping : longs intitulés CSV -> clés internes
COL_MAP = {
    'Quel est votre niveau de stress au travail ?(1 étant "pas du tout stressé" , 5 étant "extrêmement stressé )': "stress_level",
    "Ressentez-vous de la fatigue mentale au travail ?": "mental_fatigue",
    "Comment percevez-vous votre charge de travail actuelle ? Est-elle agréable, trop importante ou insuffisante ?": "workload",
    "Comment évaluez-vous la qualité de votre sommeil ?": "sleep_quality",
    "Globalement, êtes-vous satisfait(e) de votre travail ?": "job_satisfaction",
    "Vous sentez-vous reconnu(e) pour votre travail ?": "recognition",
    "Êtes-vous motivé(e) au quotidien dans votre travail ?": "motivation",
    "Avez-vous des difficultés à vous concentrer au travail ?": "concentration_difficulty",
    "Avez-vous des suggestions pour améliorer votre environnement de travail ?": "suggestions",
}

TEXT_COL = "suggestions"

# ============================================================
# 2) UTILS - nettoyage texte
# ============================================================

def clean_text(s: str) -> str:
    """
    Nettoyage léger:
    - lower
    - enlever ponctuation
    - normaliser espaces
    """
    if pd.isna(s):
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ\s'-]", " ", s)  # garder lettres FR
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ============================================================
# 3) SCORES (baseline non-IA) - pour relier NLP + bien-être
# ============================================================

FATIGUE_MAP = {"Jamais": 0, "Rarement": 1, "Parfois": 2, "Souvent": 3, "Très souvent": 4}
SLEEP_MAP   = {"Très mauvaise": 0, "Mauvaise": 1, "Moyenne": 2, "Bonne": 3, "Très bonne": 4}
SAT_MAP     = {"Très insatisfait(e)": 0, "Insatisfait(e)": 1, "Neutre": 2, "Satisfait(e)": 3, "Très satisfait(e)": 4}
YES_MAP     = {"Pas du tout": 0, "Peu": 1, "Moyennement": 2, "Oui": 3, "Oui, totalement": 4}
CONC_MAP    = {"Jamais": 0, "Parfois": 1, "Souvent": 2, "Très souvent": 3}
WORKLOAD_MAP= {"Insuffisante": -1, "Agréable": 0, "Trop importante": 1}

def add_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute des colonnes numériques + risk_score/risk_score_normalized/risk_level.
    """
    df = df.copy()

    df["stress_level"] = pd.to_numeric(df["stress_level"], errors="coerce")

    df["fatigue_num"] = df["mental_fatigue"].map(FATIGUE_MAP)
    df["sleep_num"] = df["sleep_quality"].map(SLEEP_MAP)
    df["satisfaction_num"] = df["job_satisfaction"].map(SAT_MAP)
    df["recognition_num"] = df["recognition"].map(YES_MAP)
    df["motivation_num"] = df["motivation"].map(YES_MAP)
    df["concentration_num"] = df["concentration_difficulty"].map(CONC_MAP)
    df["workload_num"] = df["workload"].map(WORKLOAD_MAP)

    # ✅ Score simple (baseline)
    df["risk_score"] = (
        df["stress_level"] * 2
        + df["fatigue_num"] * 2
        + (4 - df["sleep_num"]) * 1.5
        + df["concentration_num"] * 1.5
        + (df["workload_num"].clip(lower=0)) * 1.0
        - df["satisfaction_num"] * 1.0
        - df["motivation_num"] * 0.5
        - df["recognition_num"] * 0.5
    )

    # =========================================================
    # ✅ Normalisation sur 0..100 (basée sur min=-8, max=29.5)
    #   -8  => 0
    #   29.5 => 100
    # =========================================================
    min_score = -8.0
    max_score = 29.5
    df["risk_score_normalized"] = ((df["risk_score"] - min_score) / (max_score - min_score)) * 100

    # (optionnel mais conseillé) éviter valeurs <0 ou >100 si NA / erreurs de mapping
    df["risk_score_normalized"] = df["risk_score_normalized"].clip(lower=0, upper=100)

    def risk_level(x):
        if pd.isna(x):
            return "UNKNOWN"
        if x >= 12:
            return "HIGH"
        if x >= 7:
            return "MEDIUM"
        return "LOW"

    df["risk_level"] = df["risk_score"].apply(risk_level)
    return df
  

   


# ============================================================
# 4) NLP "performant": embeddings + clustering + topics + sentiment
# ============================================================

def choose_best_k(embeddings: np.ndarray, k_min=2, k_max=8) -> int:
    """
    Choisit K (nombre de clusters) via silhouette score.
    Sur petits datasets, k_max=8 suffit.
    """
    best_k = k_min
    best_score = -1

    for k in range(k_min, min(k_max, len(embeddings)-1) + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = km.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels)
        if score > best_score:
            best_score = score
            best_k = k

    return best_k


def extract_cluster_keywords(texts, labels, top_n=8):
    """
    Donne des mots-clés par cluster avec TF-IDF.
    C’est une approche simple mais efficace pour "nommer" les topics.
    """
    results = {}

    vect = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words=None  # option: ajouter stopwords FR
    )
    X = vect.fit_transform(texts)
    feature_names = np.array(vect.get_feature_names_out())

    for c in sorted(set(labels)):
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue

        # moyenne TF-IDF des docs du cluster
        mean_tfidf = np.asarray(X[idx].mean(axis=0)).ravel()
        top_idx = mean_tfidf.argsort()[::-1][:top_n]
        results[int(c)] = feature_names[top_idx].tolist()

    return results


def run_nlp_analysis(df: pd.DataFrame) -> dict:
    """
    Analyse NLP globale sur la colonne suggestions:
    - embeddings
    - clustering
    - keywords/topics
    - sentiment
    """
    df = df.copy()

    # Nettoyage texte
    df["suggestions_clean"] = df[TEXT_COL].apply(clean_text)
    texts = df["suggestions_clean"].tolist()

    # Garder uniquement les lignes non vides
    non_empty_idx = [i for i, t in enumerate(texts) if t.strip() != ""]
    texts_ne = [texts[i] for i in non_empty_idx]

    if len(texts_ne) < 3:
        return {
            "ok": False,
            "message": "Pas assez de texte dans suggestions pour faire une analyse NLP robuste.",
            "n_texts": len(texts_ne)
        }

    # 1) Embeddings (très important: compréhension sémantique)
    # Modèle multilingue robuste (rapide + performant)
    embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    embeddings = embedder.encode(texts_ne, normalize_embeddings=True, show_progress_bar=True)

    # 2) Clustering
    best_k = choose_best_k(embeddings, k_min=2, k_max=8)
    km = KMeans(n_clusters=best_k, random_state=42, n_init="auto")
    labels = km.fit_predict(embeddings)

    # 3) Keywords / topic names (TF-IDF par cluster)
    keywords_by_cluster = extract_cluster_keywords(texts_ne, labels, top_n=8)

    # 4) Sentiment (multilingue)
    # Modèle simple & stable: sentiment-analysis multilingue
    # (Si tu veux 100% FR-only, on peut switcher sur CamemBERT + fine-tune plus tard)
    sent_pipe = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

    sentiments = []
    for t in texts_ne:
        # le modèle renvoie des "1 star" à "5 stars"
        out = sent_pipe(t[:512])[0]
        sentiments.append(out)

    # assembler résultats par texte
    detailed = []
    for i, idx in enumerate(non_empty_idx):
        detailed.append({
            "row_index": int(idx),
            "suggestion": df.loc[idx, TEXT_COL],
            "clean": texts[i],
            "cluster": int(labels[i]),
            "sentiment": sentiments[i],
            "risk_level": df.loc[idx, "risk_level"] if "risk_level" in df.columns else None,
            "risk_score": float(df.loc[idx, "risk_score"]) if "risk_score" in df.columns else None,
        })

    # Stat cluster distribution
    cluster_counts = pd.Series(labels).value_counts().sort_index().to_dict()

    return {
        "ok": True,
        "n_texts": len(texts_ne),
        "best_k": int(best_k),
        "cluster_counts": {int(k): int(v) for k, v in cluster_counts.items()},
        "keywords_by_cluster": keywords_by_cluster,
        "detailed": detailed,
    }


# ============================================================
# 5) EXPORTS "LLM-ready"
# ============================================================

def build_llm_summary(df: pd.DataFrame, nlp_result: dict) -> dict:
    """
    Produit un résumé structuré (JSON) que tu peux donner à un LLM
    pour générer le prochain questionnaire personnalisé.
    """
    summary = {}

    # stats globales
    summary["global"] = {
        "n_rows": int(len(df)),
        "risk_distribution": df["risk_level"].value_counts().to_dict() if "risk_level" in df.columns else {},
        "avg_risk_score": float(df["risk_score"].mean()) if "risk_score" in df.columns else None,
        "avg_risk_score_normalized": float(df["risk_score_normalized"].mean())
            if "risk_score_normalized" in df.columns else None,
    }

    # topics NLP
    if nlp_result.get("ok"):
        summary["topics"] = []
        for c, kw in nlp_result["keywords_by_cluster"].items():
            summary["topics"].append({
                "cluster": int(c),
                "keywords": kw,
                "count": int(nlp_result["cluster_counts"].get(int(c), 0)),
            })

        # exemples (2) par cluster pour guider le LLM
        examples = {}
        for item in nlp_result["detailed"]:
            c = item["cluster"]
            examples.setdefault(c, [])
            if len(examples[c]) < 2:
                examples[c].append(item["suggestion"])
        summary["topic_examples"] = {str(k): v for k, v in examples.items()}
    else:
        summary["topics_error"] = nlp_result.get("message")

    return summary
# def analyze_posture_frame(frame):
#     """
#     Analyse une frame et retourne :
#     - torso_angle : angle du torse (0-180)
#     - shoulder_asym : asymétrie des épaules (0-1)
    
#     Ici, c'est un exemple simple avec détection de contours.
#     Remplace par ton vrai modèle ML ou pipeline JSON.
#     """
#     gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
#     # Détection de contours simples pour torse (fictif)
#     edges = cv2.Canny(gray, 50, 150)
#     contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
#     torso_angle = 0
#     shoulder_asym = 0

#     if contours:
#         # Choisir le plus grand contour (fictif comme torse)
#         c = max(contours, key=cv2.contourArea)
#         x, y, w, h = cv2.boundingRect(c)
        
#         # Torso angle approximatif par rapport à la verticale
#         torso_angle = 180 * (w / (h + 1e-5))  # simple ratio w/h, à remplacer par vrai angle ML

#         # Shoulder asymétrie approximative
#         shoulder_asym = abs((x + w/2) - frame.shape[1]/2) / (frame.shape[1]/2)

#     return torso_angle, shoulder_asym

#analyse une image (frame) pour extraire des informations sur la posture humaine.
#fonction en marche pour analyser une frame d'image et retourner des métriques de posture, comme l'angle du torse et l'asymétrie des épaules.
# def analyze_posture_frame(frame):
#     """
#     Analyse une frame et retourne :
#     - torso_angle : angle du torse en degrés
#     - shoulder_asym : asymétrie des épaules (0 = symétrique, 1 = max)
#     - landmarks : dictionnaire des coordonnées clés
#     """
#     frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
#         results = pose.process(frame_rgb)

#     torso_angle = 0
#     shoulder_asym = 0
#     landmarks = {}

#     if results.pose_landmarks:
#         lm = results.pose_landmarks.landmark

#         # Keypoints des épaules et hanches
#         left_shoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
#         right_shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
#         left_hip = lm[mp_pose.PoseLandmark.LEFT_HIP]
#         right_hip = lm[mp_pose.PoseLandmark.RIGHT_HIP]

#         # Calculs
#         mid_shoulder_x = (left_shoulder.x + right_shoulder.x) / 2
#         mid_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
#         mid_hip_x = (left_hip.x + right_hip.x) / 2
#         mid_hip_y = (left_hip.y + right_hip.y) / 2

#         dx = mid_hip_x - mid_shoulder_x
#         dy = mid_hip_y - mid_shoulder_y
#         torso_angle = abs(math.degrees(math.atan2(dy, dx)) - 90)  # 0 = droit, plus = penché

#         shoulder_asym = abs(left_shoulder.x - right_shoulder.x)

#         # Landmarks pour visualisation
#         landmarks = {
#             'left_shoulder': (left_shoulder.x, left_shoulder.y),
#             'right_shoulder': (right_shoulder.x, right_shoulder.y),
#             'mid_shoulder': (mid_shoulder_x, mid_shoulder_y),
#             'mid_hip': (mid_hip_x, mid_hip_y)
#         }

#     return torso_angle, shoulder_asym, landmarks









#nouvelle fonction d'analyse de posture utilisant MediaPipe pour extraire des landmarks et calculer des métriques de posture plus précises. Cette fonction est conçue pour être utilisée dans un contexte de traitement vidéo en temps réel, comme dans une application Django qui reçoit des frames vidéo du frontend. et ++
# ================================
# DETECTION POSTURE AVANCEE
# ================================
def analyze_posture_frame(frame):

    """
    Analyse une frame et retourne :
    - torso_angle : angle du torse
    - shoulder_asym : asymétrie des épaules
    - landmarks : points utiles
    - posture_flags : détection posture avancée
    """

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as pose:

        results = pose.process(frame_rgb)

    torso_angle = 0
    shoulder_asym = 0
    landmarks = {}

    posture_flags = {
    "tete_penchee": False,
    "cou_vers_avant": False,
    "epaules_arrondies": False,
    "dos_courbe": False,
    "fatigue_visuelle": False
    }

    if results.pose_landmarks:

        lm = results.pose_landmarks.landmark

        # ================================
        # LANDMARKS
        # ================================

        nose = lm[mp_pose.PoseLandmark.NOSE]

        left_ear = lm[mp_pose.PoseLandmark.LEFT_EAR]
        right_ear = lm[mp_pose.PoseLandmark.RIGHT_EAR]

        left_shoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]

        left_hip = lm[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = lm[mp_pose.PoseLandmark.RIGHT_HIP]

        # ================================
        # CALCUL CENTRES
        # ================================

        mid_shoulder_x = (left_shoulder.x + right_shoulder.x) / 2
        mid_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2

        mid_hip_x = (left_hip.x + right_hip.x) / 2
        mid_hip_y = (left_hip.y + right_hip.y) / 2

        # ================================
        # ANGLE DU TORSE
        # ================================

        dx = mid_hip_x - mid_shoulder_x
        dy = mid_hip_y - mid_shoulder_y

        torso_angle = abs(math.degrees(math.atan2(dy, dx)) - 90)

        # asymétrie épaules
        shoulder_asym = abs(left_shoulder.y - right_shoulder.y)

        # ================================
        # 1️⃣ TETE PENCHEE
        # ================================

        tete_penchee = abs(left_ear.y - right_ear.y)

        if tete_penchee > 0.03:
            posture_flags["tete_penchee"] = True

        # ================================
        # 2️⃣ COU VERS L'AVANT
        # ================================

        mid_ear_x = (left_ear.x + right_ear.x) / 2

        if (mid_ear_x - mid_shoulder_x) > 0.05:
            posture_flags["cou_vers_avant"] = True

        # ================================
        # 3️⃣ EPAULES ARRONDIES
        # ================================

        shoulder_forward = mid_shoulder_x - mid_hip_x

        if shoulder_forward > 0.04:
            posture_flags["epaules_arrondies"] = True

        # ================================
        # 4️⃣ DOS COURBE
        # ================================

        if torso_angle > 15:
            posture_flags["dos_courbe"] = True

        # ================================
        # 5️⃣ FATIGUE VISUELLE
        # ================================

        distance_head_screen = abs(nose.z)

        if distance_head_screen < 0.15:
            posture_flags["fatigue_visuelle"] = True

        # ================================
        # LANDMARKS POUR DESSIN
        # ================================

        landmarks = {
            "left_shoulder": (left_shoulder.x, left_shoulder.y),
            "right_shoulder": (right_shoulder.x, right_shoulder.y),
            "mid_shoulder": (mid_shoulder_x, mid_shoulder_y),
            "mid_hip": (mid_hip_x, mid_hip_y)
        }

    return torso_angle, shoulder_asym, landmarks, posture_flags




mp_face = mp.solutions.face_mesh

# -------------------------------
# CONSTANTES
# -------------------------------
EAR_THRESHOLD = 0.25          # seuil pour clignement
EAR_CONSEC_FRAMES = 3         # nb frames pour valider un blink
ALERT_INTERVAL = 20           # secondes entre chaque alerte

def eye_aspect_ratio(eye):
    """Calcul du Eye Aspect Ratio pour détecter clignements"""
    A = np.linalg.norm(np.array(eye[1]) - np.array(eye[5]))
    B = np.linalg.norm(np.array(eye[2]) - np.array(eye[4]))
    C = np.linalg.norm(np.array(eye[0]) - np.array(eye[3]))
    return (A + B) / (2.0 * C)


# --- AJOUTER CE CODE JUSTE APRÈS LA FONCTION eye_aspect_ratio ---

def calculate_ear_metrics(ear_history, blink_count, total_time_sec):
    """
    Calcule toutes les métriques avancées de fatigue visuelle
    en se basant sur l'historique des valeurs EAR.
    """
    if total_time_sec <= 0 or not ear_history:
        return None

    # 1. Taux de clignements par minute (Blink Rate)
    # Normal : entre 15 et 20 clignements par minute
    blink_rate_per_min = (blink_count / total_time_sec) * 60

    # 2. PERCLOS (% de temps où l'œil est fermé sous le seuil)
    # Calcule le ratio de frames fermées par rapport au total
    frames_closed = sum(1 for ear in ear_history if ear < EAR_THRESHOLD)
    perclos = (frames_closed / len(ear_history)) * 100

    # 3. Métriques statistiques de stabilité
    ear_mean = float(np.mean(ear_history))
    ear_std = float(np.std(ear_history)) # La variabilité (instabilité oculaire)

    # 4. Détection des Micro-sommeils (> 2 secondes les yeux fermés)
    # Le frontend envoie 1 frame toutes les 300ms. 2 secondes = ~7 frames consécutives.
    microsleep_count = 0
    consecutive_closed = 0
    for ear in ear_history:
        if ear < EAR_THRESHOLD:
            consecutive_closed += 1
            if consecutive_closed == 7:  # Déclenchement à 2.1 secondes
                microsleep_count += 1
        else:
            consecutive_closed = 0

    # 5. Calcul du Score de Fatigue Visuelle (0 = Reposé, 100 = Épuisé)
    fatigue_score = 0
    
    # Pénalité PERCLOS (fatigue lourde)
    if perclos > 15:
        fatigue_score += 50
    elif perclos > 10:
        fatigue_score += 30
    elif perclos > 5:
        fatigue_score += 15

    # Pénalité clignements (trop bas = fixation/fatigue, trop haut = irritation)
    if blink_rate_per_min < 10:
        fatigue_score += 25
    elif blink_rate_per_min > 25:
        fatigue_score += 20

    # Pénalité micro-sommeils (danger critique)
    fatigue_score += min(microsleep_count * 25, 50)

    # Limiter le score entre 0 et 100
    visual_fatigue_score = min(max(fatigue_score, 0), 100)

    return {
        "blink_rate_per_min": round(blink_rate_per_min, 1),
        "perclos": round(perclos, 1),
        "ear_mean": round(ear_mean, 3),
        "ear_std": round(ear_std, 3),
        "microsleep_count": microsleep_count,
        "visual_fatigue_score": round(visual_fatigue_score, 0)
    }
    
# ============================================================
# 6) MAIN
# ============================================================

def main():
    df = pd.read_csv(CSV_PATH)
    df = df.rename(columns=COL_MAP)

    # baseline score
    df = add_risk_score(df)

    # NLP
    nlp_result = run_nlp_analysis(df)

    # exports
    out_dir = os.path.join(BASE_DIR, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    df_out = os.path.join(out_dir, "df_baseline.csv")
    df.to_csv(df_out, index=False, encoding="utf-8")

    nlp_out = os.path.join(out_dir, "nlp_result.json")
    with open(nlp_out, "w", encoding="utf-8") as f:
        json.dump(nlp_result, f, ensure_ascii=False, indent=2)

    llm_summary = build_llm_summary(df, nlp_result)
    llm_out = os.path.join(out_dir, "llm_summary.json")
    with open(llm_out, "w", encoding="utf-8") as f:
        json.dump(llm_summary, f, ensure_ascii=False, indent=2)

    print("✅ Terminé")
    print("CSV baseline:", df_out)
    print("NLP json:", nlp_out)
    print("LLM summary:", llm_out)


if __name__ == "__main__":
    print("BASE_DIR =", BASE_DIR)
    main()