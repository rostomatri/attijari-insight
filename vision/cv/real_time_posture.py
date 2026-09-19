#test de posture en temps réel avec OpenCV et ton modèle ML
# -*- coding: utf-8 -*-
from tkinter import font

from tkinter import font

from matplotlib.pyplot import draw, text
from sklearn import metrics
import cv2
import numpy as np
from surveys.analytics.baseline_nlp import analyze_posture_frame  # exemple : ta fonction ML
from PIL import Image, ImageDraw, ImageFont
import numpy as np
# def draw_posture(frame, torso_angle, shoulder_asym):
#     """
#     Dessine les informations de posture sur la frame.
#     """
#     # Texte sur la frame
#     cv2.putText(frame, f"Torso angle: {torso_angle:.2f}", (30,50),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
#     cv2.putText(frame, f"Shoulder asymmetry: {shoulder_asym:.2f}", (30,80),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

#     # Optionnel : dessin du torse (rectangle fictif)
#     center = (frame.shape[1]//2, frame.shape[0]//2)
#     size = 100
#     cv2.rectangle(frame,
#                   (center[0]-size, center[1]-size),
#                   (center[0]+size, center[1]+size),
#                   (255,0,0), 2)




def real_time_posture():
    cap = cv2.VideoCapture(0)  # webcam par défaut
    if not cap.isOpened():
        print("Impossible d'ouvrir la webcam")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # -----------------------------
        # 1. Prétraitement de la frame si nécessaire
        # frame = preprocess_frame(frame)
        # -----------------------------

        # 2. Analyse avec ton modèle ML
        try:
            torso_angle, shoulder_asym, landmarks = analyze_posture_frame(frame)
        except Exception as e:
            print("Erreur modèle :", e)
            torso_angle, shoulder_asym, landmarks = 0, 0, {}

        # 3. Dessin sur la frame
        metrics_data = {
          "score": score,
          "blink_count": blink_counter,
          "posture_time": posture_time,
          "eye_closed_time": eye_closed_time
        }

        if landmarks:
            
            draw_posture(frame, torso_angle, shoulder_asym, landmarks)

        # 4. Affichage en temps réel
        cv2.imshow("Posture Live", frame)

        # 5. Quitter avec 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

#test de score ergonomique maintenant jutulise score 
def compute_ergonomic_score(posture_flags, blink_total=0):
    """Score 100 → déduction selon mauvaises postures / fatigue"""
    score = 100
    if posture_flags.get("dos_courbe"): score -= 20
    if posture_flags.get("cou_vers_avant"): score -= 15
    if posture_flags.get("tete_penchee"): score -= 10
    if posture_flags.get("epaules_arrondies"): score -= 10
    if posture_flags.get("fatigue_visuelle"): score -= 15
    if blink_total > 30: score -= 10
    return max(score, 0)


#les fonction appeles dans views.py

#appele dans views 
def draw_posture(frame, torso_angle, shoulder_asym, landmarks,posture_flags=None, metrics=None):
    """
    Dessine les informations de posture sur la frame.
    Utilise Pillow pour afficher correctement les accents.
    """

    # ================================
    # 1️⃣ CONVERSION OPENCV → PIL
    # ================================

    img_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(img_pil)

    # police support accents
    font = ImageFont.truetype("arial.ttf", 28)

    # ================================
    # 2️⃣ TEXTE AVEC ACCENTS
    # ================================

    draw.text(
        (40, 50),
        f"Angle du torse : {torso_angle:.2f}",
        font=font,
        fill=(255, 0, 0)
    )

    draw.text(
        (30, 80),
        f"Asymétrie des épaules : {shoulder_asym:.2f}",
        font=font,
        fill=(0, 255, 0)
    )
# ================================
# 🔥 AJOUT METRICS TEMPS RÉEL
# ================================

    if metrics:
        y = 130

        def draw_line(text):
            nonlocal y
            draw.text((40, y), text, font=font, fill=(255, 255, 0))
            y += 35

        draw_line(f"Clignements : {metrics.get('blink_count', 0)}")

        posture_time = metrics.get("posture_time", {})

        draw_line(f"Dos courbé : {posture_time.get('dos_courbe', 0):.1f}s")
        draw_line(f"Cou vers avant : {posture_time.get('cou_vers_avant', 0):.1f}s")
        draw_line(f"Tête penchée : {posture_time.get('tete_penchee', 0):.1f}s")
        draw_line(f"Épaules arrondies : {posture_time.get('epaules_arrondies', 0):.1f}s")

        draw_line(f"Yeux fermés : {metrics.get('eye_closed_time', 0):.1f}s")
        print("Landmarks détectés:", landmarks)
        t = metrics.get('total_time', 0)
        minutes = int(t // 60)
        seconds = int(t % 60)

        draw_line(f"Durée : {minutes}m {seconds}s")
    # ================================
    # 3️⃣ CONVERSION PIL → OPENCV
    # ================================

    frame = np.array(img_pil)

    # ================================
    # 4️⃣ DESSIN DES POINTS AVEC OPENCV
    # ================================

    h, w, _ = frame.shape

    left_shoulder = landmarks['left_shoulder']
    right_shoulder = landmarks['right_shoulder']
    mid_shoulder = landmarks['mid_shoulder']
    mid_hip = landmarks['mid_hip']

    # points
    cv2.circle(frame, (int(left_shoulder[0] * w), int(left_shoulder[1] * h)), 5, (0, 0, 255), -1)
    cv2.circle(frame, (int(right_shoulder[0] * w), int(right_shoulder[1] * h)), 5, (0, 0, 255), -1)

    cv2.circle(frame, (int(mid_shoulder[0] * w), int(mid_shoulder[1] * h)), 5, (255, 0, 0), -1)
    cv2.circle(frame, (int(mid_hip[0] * w), int(mid_hip[1] * h)), 5, (255, 0, 0), -1)

    # ligne torse
    cv2.line(
        frame,
        (int(mid_shoulder[0] * w), int(mid_shoulder[1] * h)),
        (int(mid_hip[0] * w), int(mid_hip[1] * h)),
        (0, 255, 0),
        2
    )
    # # si posture_flags fourni, ajouter texte OpenCV
    # if posture_flags:
    #     y = 120
    #     for key, text in [("cou_vers_avant", "Cou vers l'avant"),
    #                       ("tete_penchee", "Têtee penchée"),
    #                       ("epaules_arrondies", "Épaules arrondies"),
    #                       ("dos_courbe", "Dos courbé"),
    #                       ("fatigue_visuelle", "Fatigue visuelle détectée")]:
    #         if posture_flags.get(key):
    #             cv2.putText(frame, text, (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
    #             y += 30
    return frame



#test de diagnostique
# real_time_posture.py ou diagnostic.py

def generate_diagnostic_report(metrics):
    total_time = metrics.get("total_time", 1)  # éviter div par 0
    posture_time = metrics.get("posture_time", {})
    eye_closed_time = metrics.get("eye_closed_time", 0)
    blink_count = metrics.get("blink_count", 0)
    score = metrics.get("score", 0)

    # Calcul % mauvaises postures
    dos_courbe_pct = (posture_time.get("dos_courbe", 0) / total_time) * 100
    tete_penchee_pct = (posture_time.get("tete_penchee", 0) / total_time) * 100
    epaules_arrondies_pct = (posture_time.get("epaules_arrondies", 0) / total_time) * 100
    cou_avant_pct = (posture_time.get("cou_vers_avant", 0) / total_time) * 100

    report = {
        "total_time_min": total_time / 60,
        "mauvaise_posture": {
            "dos_courbe": {"time_sec": posture_time.get("dos_courbe",0), "pct": dos_courbe_pct},
            "tete_penchee": {"time_sec": posture_time.get("tete_penchee",0), "pct": tete_penchee_pct},
            "epaules_arrondies": {"time_sec": posture_time.get("epaules_arrondies",0), "pct": epaules_arrondies_pct},
            "cou_vers_avant": {"time_sec": posture_time.get("cou_vers_avant",0), "pct": cou_avant_pct},
        },
        "score_posture": score,
        "clignements": blink_count,
        "temps_yeux_fermes_sec": eye_closed_time,
        "recommendations": [],
    }

    # Recommandations simples
    if dos_courbe_pct > 10 or tete_penchee_pct > 10:
        report["recommendations"].append(
            "Prenez des pauses régulières, redressez votre dos et surveillez votre posture."
        )
    if eye_closed_time/total_time > 0.1:
        report["recommendations"].append(
            "Fatigue visuelle détectée, reposez vos yeux 5-10 minutes toutes les heures."
        )
    if blink_count < 10:
        report["recommendations"].append(
            "Vous clignez peu des yeux, pensez à hydrater vos yeux."
        )

    return report
if __name__ == "__main__":
    real_time_posture()