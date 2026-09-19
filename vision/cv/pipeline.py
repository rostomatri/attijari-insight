import cv2
import numpy as np
import mediapipe as mp
import os
from surveys.analytics.baseline_nlp import analyze_posture_frame  

import logging
logger = logging.getLogger(__name__)
logger.info("Message de debug")

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def _angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    cosang = np.clip(cosang, -1.0, 1.0)

    return float(np.degrees(np.arccos(cosang)))



def run_cv_pipeline(video_path: str, fps_used: int = 10, metrics=None):

    import logging
    logger = logging.getLogger(__name__)
    logger.info("🚀 START run_cv_pipeline")

    bad_posture_pct = 0
    good_pct = 100
    posture_status = "UNKNOWN"
    posture_score = 0
    segments = []
    duration_sec = 0

    total_used = 0
    bad_frames = 0
    seg_open = None
    BAD_MIN_SEC = 3.0

    # 🔥 METRICS récupérées depuis analyze_posture_frame
    total_time = 0.0
    eye_closed_time = 0.0
    blink_counter = 0
    posture_time = {
        "tete_penchee": 0.0,
        "cou_vers_avant": 0.0,
        "epaules_arrondies": 0.0,
        "dos_courbe": 0.0,
        "fatigue_visuelle": 0.0
    }
    # 🔹 OPEN VIDEO
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Impossible d'ouvrir la vidéo")

    fps_orig = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps_orig if total_frames > 0 else 0

    step = max(int(round(fps_orig / fps_used)), 1)

    writer = None
    frame_index = 0

    with mp_pose.Pose() as pose:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % step != 0:
                frame_index += 1
                continue

            t = frame_index / fps_orig
            total_used += 1

            # 🔥 ICI ON UTILISE analyze_posture_frame
            result = analyze_posture_frame(frame)

            if result:
                torso_angle, shoulder_asym, landmarks, posture_flags = result

                # 🔥 ON RECUPERE LES METRICS
                if metrics:
                    total_time = metrics.get("total_time", total_time)
                    eye_closed_time = metrics.get("eye_closed_time", eye_closed_time)
                    blink_counter = metrics.get("blink_count", blink_counter)

                    pt = metrics.get("posture_time", {})
                    for key in posture_time:
                        posture_time[key] = pt.get(key, posture_time[key])

                # 🔥 LOG DEBUG
                logger.info(f"Metrics frame {frame_index}: {metrics}")

                # posture
                is_bad = (torso_angle > 15) or (shoulder_asym > 0.06)

                if is_bad:
                    bad_frames += 1
                    if seg_open is None:
                        seg_open = {"start": t}
                else:
                    if seg_open:
                        if (t - seg_open["start"]) >= BAD_MIN_SEC:
                            segments.append({
                                "type": "BAD_POSTURE",
                                "start_sec": float(seg_open["start"]),
                                "end_sec": float(t),
                                "severity": 4
                            })
                        seg_open = None

            frame_index += 1

    cap.release()

    # 🔥 CALCUL FINAL
    if total_used > 0:
        bad_posture_pct = (bad_frames / total_used) * 100
        good_pct = 100 - bad_posture_pct

    posture_status = (
        "Bonne" if good_pct >= 80 else
        "Acceptable" if good_pct >= 50 else
        "Mauvaise"
    )

    posture_score = good_pct

    logger.info("✅ END run_cv_pipeline")

    return {
        "posture_score": posture_score,
        "posture_status": posture_status,
        "bad_posture_pct": bad_posture_pct,
        "good_posture_pct": good_pct,
        "segments": segments,
        "duration_sec": duration_sec,

        # 🔥 METRICS DEPUIS DB
        "total_time": metrics.get("total_time", 0) if metrics else 0,
        "eye_closed_time": metrics.get("eye_closed_time", 0) if metrics else 0,
        "blink_count": metrics.get("blink_count", 0) if metrics else 0,
        "posture_time": metrics.get("posture_time", {}) if metrics else {}
    }