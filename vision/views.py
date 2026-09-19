# -*- coding: utf-8 -*-
import time

from anyio import current_time
from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from httpx import request
import cv2
import numpy as np
import base64
from django.core.files import File
# from vision.cv.real_time_posture import analyze_posture_frame, draw_posture

# from surveys.analytics import real_time_posture
from surveys.analytics.baseline_nlp import calculate_ear_metrics
from surveys.analytics.baseline_nlp import analyze_posture_frame
from surveys.models import Employee, PostureMetric
from vision.cv.medical_rules import detect_symptoms
from vision.cv.real_time_posture import draw_posture
from .models import RealtimeMetrics, VideoUpload, VideoAnalysisResult, VideoSegment
from .tasks import analyze_video
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from vision.cv.real_time_posture import  compute_ergonomic_score
from surveys.analytics.baseline_nlp import eye_aspect_ratio,mp_face, EAR_THRESHOLD, EAR_CONSEC_FRAMES
from sklearn import metrics
from vision.cv.report_builder import build_full_report
from vision.cv.llm_service import generate_medical_text
@csrf_exempt
def upload_video(request):

    if request.method != "POST":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    employee_id = request.POST.get("employee_id")

    if not employee_id:
        return JsonResponse({"message": "employee_id requis"}, status=400)

    try:
        emp = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({"message": "Employee introuvable"}, status=404)

    if not emp:
        return JsonResponse({"message": "Employee introuvable"}, status=404)


    # ================================
    # ❌ PARTIE INTERDITE DANS DJANGO VIEW
    # ================================
    # Une view Django ne doit pas ouvrir la webcam
    # ni afficher une fenêtre OpenCV
    #
    # car le serveur Django n'est pas l'ordinateur de l'utilisateur.
    #
    # Cette partie est donc commentée mais conservée pour référence
    # ================================


    '''
    video = cv2.VideoCapture(0)

    if not video.isOpened():
        return JsonResponse({"message": "Impossible d'ouvrir la webcam"}, status=500)

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter('output.avi', fourcc, 20.0, (640, 480))

    try:
        while True:

            ret, frame = video.read()

            if not ret:
                break

            # analyse posture temps réel
            try:
                torso_angle, shoulder_asym, landmarks = analyze_posture_frame(frame)

                if landmarks:
                    draw_posture(frame, torso_angle, shoulder_asym, landmarks)

            except Exception as e:
                print("Erreur dans l'analyse de la posture :", e)

            # affichage OpenCV
            cv2.imshow('Real-Time Posture Tracking', frame)

            # sauvegarde vidéo
            out.write(frame)

            # quitter avec q
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:

        video.release()
        out.release()
        cv2.destroyAllWindows()
    '''


    # ================================
    # ✔ BON FONCTIONNEMENT DJANGO
    # ================================
    # La vidéo doit venir du frontend
    # via FormData
    # ================================

    video_file = request.FILES.get("video")
    metrics_json = request.POST.get("metrics")  # 🔹 récupère le JSON envoyé
    metrics_data = None
    if metrics_json:
        try:
            metrics_data = json.loads(metrics_json)
        except json.JSONDecodeError:
            metrics_data = None


    if not video_file:
        return JsonResponse({"message": "video manquante"}, status=400)


    # sauvegarde vidéo dans la base
    upload = VideoUpload.objects.create(
        employee=emp,
        video_file=video_file,
        status="PENDING"
    )

    # 🔹 Stockage des métriques finales de la vidéo (Snapshot)
    if metrics_data:
        # On récupère l'employé
        employee = Employee.objects.get(id=employee_id)
        
        # On enregistre TOUTES les données de fatigue visuelle reçues du frontend
        RealtimeMetrics.objects.create(
            employee=employee,
            total_time=metrics_data.get("total_time", 0),
            eye_closed_time=metrics_data.get("eye_closed_time", 0),
            blink_count=metrics_data.get("blink_count", 0),
            posture_time=metrics_data.get("posture_time", {}),
            # ✅ AJOUT DES NOUVEAUX CHAMPS DE FATIGUE
            ear_history=metrics_data.get("ear_history", []),
            blink_rate_per_min=metrics_data.get("blink_rate_per_min", 0),
            perclos=metrics_data.get("perclos", 0),
            visual_fatigue_score=metrics_data.get("visual_fatigue_score", 0),
            microsleep_count=metrics_data.get("microsleep_count", 0)
        )
        print("✅ Métriques de fatigue sauvegardées avec succès lors de l'upload.")
    
    # lancement analyse asynchrone Celery
    analyze_video.delay(upload.id)


    return JsonResponse({
        "upload_id": upload.id,
        "status": upload.status
    }, status=201)



@csrf_exempt
def video_status(request, upload_id: int):

    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    up = VideoUpload.objects.filter(id=upload_id).first()

    if not up:
        return JsonResponse({"message": "Upload introuvable"}, status=404)

    return JsonResponse({
        "upload_id": up.id,
        "status": up.status,
        "error_message": up.error_message,
        "duration_sec": up.duration_sec,
    }, status=200)



@csrf_exempt
def video_result(request, upload_id: int):

    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    up = VideoUpload.objects.filter(id=upload_id).first()

    if not up:
        return JsonResponse({"message": "Upload introuvable"}, status=404)

    res = VideoAnalysisResult.objects.filter(upload=up).first()

    if not res:
        return JsonResponse({
            "message": "Result not ready",
            "status": up.status
        }, status=200)

    segs = list(
        VideoSegment.objects
        .filter(upload=up)
        .values("type", "start_sec", "end_sec", "severity", "meta")
    )

    return JsonResponse({
        "upload_id": up.id,
        "employee_id": up.employee_id,
        "status": up.status,
        "posture": {
            "score": res.posture_score,
            "status": res.posture_status,
            "bad_posture_pct": res.bad_posture_pct,
        },
        "segments": segs,
        "summary_text": res.summary_text,
    }, status=200)



# def run_real_time_posture(request):
#     """
#     Vue de test pour lancer la détection posture locale
#     (debug seulement)
#     """

#     try:

#         # ⚠ uniquement pour test local
#         real_time_posture()

#         return JsonResponse({
#             "status": "success",
#             "message": "Real-time posture executed successfully"
#         })

#     except Exception as e:

#         return JsonResponse({
#             "status": "error",
#             "message": str(e)
#         })
    
# état global pour alertes et clignements 
# last_alert_time = time.time() 
# blink_counter = 0 
# blink_consec = 0 
# blink_state = False # True si les yeux sont fermés 
# # Calibration utilisateur 
# ear_baseline = None 
# calibration_frames = 30 
# ear_values = [] 
# # ================================ # 
# # # 🔥 TIME TRACKING GLOBAL # 
# # # ================================ 
# import time 
# from django.http import JsonResponse
# from vision.cv.real_time_posture import generate_diagnostic_report
# posture_time = { 
#     "tete_penchee": 0, 
#     "cou_vers_avant": 0, 
#     "epaules_arrondies": 0, 
#     "dos_courbe": 0, 
#     "fatigue_visuelle": 0
#       } 
# eye_closed_time = 0 
# last_time = time.time() 
# # variables globales 
# total_time = 0 
# blink_counter = 0 
# eye_closed_time = 0 
# posture_time = { 
#     "tete_penchee": 0, 
#     "cou_vers_avant": 0, 
#     "epaules_arrondies": 0, 
#     "dos_courbe": 0, 
#     "fatigue_visuelle": 0 
#     } 
# @csrf_exempt 
# def analyze_frame(request): 
#     global last_alert_time, blink_counter, blink_consec, blink_state 
#     global posture_time, last_time, eye_closed_time 
#     global total_time 
#     score = 0 
#     if request.method != "POST": 
#         return JsonResponse({"message": "Method not allowed"}, status=405) 
    
#     image_base64 = request.POST.get("image") 
#     employee_id = request.POST.get("employee_id")
#     if not image_base64: 
#         return JsonResponse({"message": "No image provided"}, status=400) 
#     try: 
#         # ================================ 
#         # # 1️⃣ DECODE IMAGE #
#         #  ================================ 
#         img_data = base64.b64decode(image_base64) 
#         nparr = np.frombuffer(img_data, np.uint8) 
#         frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) 
#         if frame is None: 
#             return JsonResponse({"message": "Frame decode failed"}, status=400) 
#         # ================================ 
#         # # ⏱️ TEMPS ENTRE FRAMES 
#         # # ================================ 
#         current_time = time.time() 
#         delta_time = current_time - last_time 
#         last_time = current_time 
#         total_time += delta_time 
#         # ================================ 
#         # # 2️⃣ POSTURE 
#         # # ================================ 
#         torso_angle, shoulder_asym, landmarks, posture_flags = analyze_posture_frame(frame) 
#         # 🔥 TIME TRACKING POSTURE 
#         for key in posture_time: 
#             if posture_flags.get(key): 
#                 posture_time[key] += delta_time 
#         metrics_data = { 
#             "blink_count": blink_counter, 
#             "posture_time": posture_time, 
#             "eye_closed_time": eye_closed_time, 
#             "total_time": total_time , 
#             "score": score, 
#             }
#         if landmarks: 
#             frame = draw_posture(frame, torso_angle, shoulder_asym, landmarks, posture_flags, metrics_data) 
#         # ================================
#         # # 3️⃣ FATIGUE VISUELLE 
#         # # ================================ 
#         frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
#         LEFT_EYE = [33, 160, 158, 133, 153, 144] 
#         RIGHT_EYE = [362, 385, 387, 263, 373, 380] 
#         h, w, _ = frame.shape 
#         ear = 0 
        
#         with mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True) as face_mesh: 
#             results = face_mesh.process(frame_rgb) 
#             if results.multi_face_landmarks: 
#                 for face_landmarks in results.multi_face_landmarks: 
#                     left_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in LEFT_EYE] 
#                     right_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in RIGHT_EYE] 
#                     left_EAR = eye_aspect_ratio(left_eye) 
#                     right_EAR = eye_aspect_ratio(right_eye) 
#                     ear = (left_EAR + right_EAR) / 2.0 
#                     if ear < EAR_THRESHOLD: 
#                         eye_closed_time += delta_time 
#                         blink_consec += 1 
#                         if blink_consec >= EAR_CONSEC_FRAMES and not blink_state: 
#                             blink_counter += 1 
#                             blink_state = True 
#                     else: 
#                         blink_consec = 0 
#                         blink_state = False 

#         # ================================ #
#         #  4️⃣ SCORE # 
#         # ================================ 
#         total_bad_time = sum(posture_time.values()) 
        
        
        
#         score = max(0, 100 - (total_bad_time * 3 + eye_closed_time * 5)) 
#         metrics_data["score"] = score
#         # ================================ #
#         #  5️⃣ ALERTES #
#         #  ================================ 
#         #diagnostic_report = generate_diagnostic_report(metrics_data)

#         if time.time() - last_alert_time > 20: 
#             print("ALERTE:", posture_flags, score) 
#             last_alert_time = time.time() 

#         # ================================ # 
#         # 6️⃣ ENCODAGE IMAGE #
#         #  ================================ 
#         _, buffer = cv2.imencode(".jpg", frame) 
#         img_base64 = base64.b64encode(buffer).decode("utf-8") 

#         from .models import RealtimeMetrics

#         employee_id = request.POST.get("employee_id")

#         # ================================
#         # 6️⃣ Enregistrement RealtimeMetrics
#         # ================================
#         if employee_id:
#             try:
#                 employee = Employee.objects.get(id=employee_id)
    
#                 # sauvegarde toutes les 5 secondes pour éviter trop de requêtes
#                 if int(total_time) % 5 == 0:
    
#                     RealtimeMetrics.objects.update_or_create(
#                         employee=employee,
#                         defaults={
#                             "total_time": total_time,
#                             "eye_closed_time": eye_closed_time,
#                             "blink_count": blink_counter,
#                             "posture_time": posture_time
#                         }
#                     )
#             except Exception as e:
#                 print("ERROR saving metrics:", e)

#         # ================================
      
       
#         return JsonResponse({"image": img_base64, "metrics": metrics_data})

#     except Exception as e:
#         print("ERROR:", str(e))
#         return JsonResponse({"message": str(e)}, status=500)

#     # 🔥 Sécurité : return par défaut
#     return JsonResponse({"message": "Unknown error occurred"}, status=500)


#################








last_alert_time = time.time() 
blink_counter = 0 
blink_consec = 0 
blink_state = False # True si les yeux sont fermés 


# --- AJOUT ---
ear_history = []  # Va stocker la courbe oculaire de la session
# -----------


# Calibration utilisateur 
ear_baseline = None 
calibration_frames = 30 
ear_values = [] 
# ================================ # 
# # 🔥 TIME TRACKING GLOBAL # 
# # ================================ 
import time 
posture_time = { 
    "tete_penchee": 0, 
    "cou_vers_avant": 0, 
    "epaules_arrondies": 0, 
    "dos_courbe": 0, 
    "fatigue_visuelle": 0
      } 
eye_closed_time = 0 
last_time = time.time() 
# variables globales 
total_time = 0 
blink_counter = 0 
eye_closed_time = 0 
posture_time = { 
    "tete_penchee": 0, 
    "cou_vers_avant": 0, 
    "epaules_arrondies": 0, 
    "dos_courbe": 0, 
    "fatigue_visuelle": 0 
    } 
# @csrf_exempt 
# def analyze_frame(request): 
#     global last_alert_time, blink_counter, blink_consec, blink_state 
#     global posture_time, last_time, eye_closed_time 
#     global total_time 
#     if request.method != "POST": 
#         return JsonResponse({"message": "Method not allowed"}, status=405) 
    
#     image_base64 = request.POST.get("image") 
#     if not image_base64: 
#         return JsonResponse({"message": "No image provided"}, status=400) 
#     try: 
#         # ================================ 
#         # # 1️⃣ DECODE IMAGE #
#         #  ================================ 
#         img_data = base64.b64decode(image_base64) 
#         nparr = np.frombuffer(img_data, np.uint8) 
#         frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) 
#         if frame is None: 
#             return JsonResponse({"message": "Frame decode failed"}, status=400) 
#         # ================================ 
#         # # ⏱️ TEMPS ENTRE FRAMES 
#         # # ================================ 
#         current_time = time.time() 
#         delta_time = current_time - last_time 
#         last_time = current_time 
#         total_time += delta_time 
#         # ================================ 
#         # # 2️⃣ POSTURE 
#         # # ================================ 
#         torso_angle, shoulder_asym, landmarks, posture_flags = analyze_posture_frame(frame) 
#         # 🔥 TIME TRACKING POSTURE 
#         for key in posture_time: 
#             if posture_flags.get(key): 
#                 posture_time[key] += delta_time 
#         metrics_data = { 
#             "blink_count": blink_counter, 
#             "posture_time": posture_time, 
#             "eye_closed_time": eye_closed_time, 
#             "total_time": total_time 
#         } 
#         if landmarks: 
#             frame = draw_posture(frame, torso_angle, shoulder_asym, landmarks, posture_flags, metrics_data) 
#         # ================================
#         # # 3️⃣ FATIGUE VISUELLE 
#         # # ================================ 
#         frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
#         LEFT_EYE = [33, 160, 158, 133, 153, 144] 
#         RIGHT_EYE = [362, 385, 387, 263, 373, 380] 
#         h, w, _ = frame.shape 
#         ear = 0 
        
#         with mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True) as face_mesh: 
#             results = face_mesh.process(frame_rgb) 
#             if results.multi_face_landmarks: 
#                 for face_landmarks in results.multi_face_landmarks: 
#                     left_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in LEFT_EYE] 
#                     right_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in RIGHT_EYE] 
#                     left_EAR = eye_aspect_ratio(left_eye) 
#                     right_EAR = eye_aspect_ratio(right_eye) 
#                     ear = (left_EAR + right_EAR) / 2.0 
#                     if ear < EAR_THRESHOLD: 
#                         eye_closed_time += delta_time 
#                         blink_consec += 1 
#                         if blink_consec >= EAR_CONSEC_FRAMES and not blink_state: 
#                             blink_counter += 1 
#                             blink_state = True 
#                     else: 
#                         blink_consec = 0 
#                         blink_state = False 

#         # ================================ # 4️⃣ SCORE # ================================ 
#         total_bad_time = sum(posture_time.values()) 
        
#         #===========================
        
        
        
        
        
        
        
        
        
#         score = max(0, 100 - (total_bad_time * 3 + eye_closed_time * 5)) 
#         metrics_data["score"] = score 

#         # ================================ # 5️⃣ ALERTES # ================================ 
#         if time.time() - last_alert_time > 20: 
#             print("ALERTE:", posture_flags, score) 
#             last_alert_time = time.time() 

#         # ================================ # 6️⃣ ENCODAGE IMAGE # ================================ 
#         _, buffer = cv2.imencode(".jpg", frame) 
#         img_base64 = base64.b64encode(buffer).decode("utf-8") 

#         from .models import RealtimeMetrics

#         employee_id = request.POST.get("employee_id")

#         # ================================
#         # 6️⃣ Enregistrement RealtimeMetrics
#         # ================================
#         if employee_id:
#             try:
#                 employee = Employee.objects.get(id=employee_id)
#                 RealtimeMetrics.objects.update_or_create(
#                     employee=employee,
#                     defaults={
#                         "total_time": total_time,
#                         "eye_closed_time": eye_closed_time,
#                         "blink_count": blink_counter,
#                         "posture_time": posture_time
#                     }
#                 )
#             except Exception as e:
#                 print("ERROR saving metrics:", e)

#         # ================================
#         # 7️⃣ Encodage image
#         # ================================
#         _, buffer = cv2.imencode(".jpg", frame)
#         img_base64 = base64.b64encode(buffer).decode("utf-8")

#         return JsonResponse({"image": img_base64, "metrics": metrics_data})

#     except Exception as e:
#         print("ERROR:", str(e))
#         return JsonResponse({"message": str(e)}, status=500)

#     # 🔥 Sécurité : return par défaut
#     return JsonResponse({"message": "Unknown error occurred"}, status=500)

@csrf_exempt 
def analyze_frame(request): 
    global last_alert_time, blink_counter, blink_consec, blink_state 
    global posture_time, last_time, eye_closed_time 
    global total_time, ear_history  # <-- IMPORTANT: ajout de ear_history ici

    if request.method != "POST": 
        return JsonResponse({"message": "Method not allowed"}, status=405) 
    
    image_base64 = request.POST.get("image") 
    employee_id = request.POST.get("employee_id")  # Récupéré du frontend

    if not image_base64: 
        return JsonResponse({"message": "No image provided"}, status=400) 
    try: 
        # 1️⃣ DECODE IMAGE 
        img_data = base64.b64decode(image_base64) 
        nparr = np.frombuffer(img_data, np.uint8) 
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) 
        if frame is None: 
            return JsonResponse({"message": "Frame decode failed"}, status=400) 

        # ⏱️ TEMPS ENTRE FRAMES 
        current_time = time.time() 
        delta_time = current_time - last_time 
        last_time = current_time 
        total_time += delta_time 

        # 2️⃣ POSTURE 
        torso_angle, shoulder_asym, landmarks, posture_flags = analyze_posture_frame(frame) 
        for key in posture_time: 
            if posture_flags.get(key): 
                posture_time[key] += delta_time 

        metrics_data = { 
            "blink_count": blink_counter, 
            "posture_time": posture_time, 
            "eye_closed_time": eye_closed_time, 
            "total_time": total_time 
        } 

        # 3️⃣ FATIGUE VISUELLE & EAR
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
        LEFT_EYE = [33, 160, 158, 133, 153, 144] 
        RIGHT_EYE = [362, 385, 387, 263, 373, 380] 
        h, w, _ = frame.shape 
        ear = 0 
        
        with mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True) as face_mesh: 
            results = face_mesh.process(frame_rgb) 
            if results.multi_face_landmarks: 
                for face_landmarks in results.multi_face_landmarks: 
                    left_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in LEFT_EYE] 
                    right_eye = [(int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)) for i in RIGHT_EYE] 
                    left_EAR = eye_aspect_ratio(left_eye) 
                    right_EAR = eye_aspect_ratio(right_eye) 
                    ear = (left_EAR + right_EAR) / 2.0 
                    
                    # --- NOUVEAU : GESTION HISTORIQUE EAR ---
                    ear_history.append(float(ear))
                    # Garder un historique max de 200 frames (~1 minute de données à 300ms d'intervalle)
                    if len(ear_history) > 200:
                        ear_history.pop(0)
                    # ----------------------------------------

                    if ear < EAR_THRESHOLD: 
                        eye_closed_time += delta_time 
                        blink_consec += 1 
                        if blink_consec >= EAR_CONSEC_FRAMES and not blink_state: 
                            blink_counter += 1 
                            blink_state = True 
                    else: 
                        blink_consec = 0 
                        blink_state = False 

        # --- NOUVEAU : CALCUL DES MÈTRIQUES AVANCÉES ---
        visual_metrics = calculate_ear_metrics(ear_history, blink_counter, total_time)
        if visual_metrics:
            metrics_data.update(visual_metrics)
            # Ajout de l'historique pour dessiner le graphique côté React
            metrics_data["ear_history"] = ear_history
        # -----------------------------------------------

        # 4️⃣ SCORE POSTURE 
        total_bad_time = sum(posture_time.values()) 
        score = max(0, 100 - (total_bad_time * 3 + eye_closed_time * 5)) 
        metrics_data["score"] = score 

        if landmarks: 
            frame = draw_posture(frame, torso_angle, shoulder_asym, landmarks, posture_flags, metrics_data) 

        # 5️⃣ ALERTES 
        if time.time() - last_alert_time > 20: 
            last_alert_time = time.time() 

        # 6️⃣ ENREGISTREMENT EN BASE (RealtimeMetrics)
        if employee_id:
            try:
                employee = Employee.objects.get(id=employee_id)
                # Sauvegarder les données de la session
                RealtimeMetrics.objects.update_or_create(
                    employee=employee,
                    defaults={
                        "total_time": total_time,
                        "eye_closed_time": eye_closed_time,
                        "blink_count": blink_counter,
                        "posture_time": posture_time,
                        # Nouveaux champs
                        "ear_history": ear_history,
                        "blink_rate_per_min": metrics_data.get("blink_rate_per_min", 0),
                        "perclos": metrics_data.get("perclos", 0),
                        "visual_fatigue_score": metrics_data.get("visual_fatigue_score", 0),
                        "microsleep_count": metrics_data.get("microsleep_count", 0)
                    }
                )
            except Exception as e:
                print("ERROR saving metrics:", e)

        # 7️⃣ ENCODAGE IMAGE RETOUR
        _, buffer = cv2.imencode(".jpg", frame) 
        img_base64 = base64.b64encode(buffer).decode("utf-8") 

        return JsonResponse({"image": img_base64, "metrics": metrics_data})

    except Exception as e:
        print("ERROR:", str(e))
        return JsonResponse({"message": str(e)}, status=500)

from django.utils import timezone
from datetime import datetime, timedelta

@csrf_exempt
def daily_report(request, employee_id):
    today = timezone.now().date()
    metrics_today = RealtimeMetrics.objects.filter(employee__id=employee_id, created_at__date=today)
    
    if not metrics_today.exists():
        return JsonResponse({
            "report": "No metrics today",
            "metrics": {},
            "llm_report": "Aucune donnée disponible"
        })
    # Récupérer la dernière session sauvegardée de la journée
    last_session = metrics_today.last()

    # 🔹 2. SCORE depuis PostureMetric
    posture_metrics_today = PostureMetric.objects.filter(
        employee_id=employee_id,
        created_at__date=today
    )
    if posture_metrics_today.exists():
        score = sum(m.score for m in posture_metrics_today) / len(posture_metrics_today)
    else:
        score = 0  # fallback
        
    # 🔹 Aggrégation metrics
    agg_metrics = {
        "score": score,
        "total_time": sum(v.total_time for v in metrics_today),
        "posture_time": {
        # "score": sum(v.metrics.get("score", 0) for v in metrics_today) / max(len(metrics_today), 1),
            "dos_courbe": sum(v.posture_time.get("dos_courbe", 0) for v in metrics_today),
            "tete_penchee": sum(v.posture_time.get("tete_penchee", 0) for v in metrics_today),
            "cou_vers_avant": sum(v.posture_time.get("cou_vers_avant", 0) for v in metrics_today),
            "epaules_arrondies": sum(v.posture_time.get("epaules_arrondies", 0) for v in metrics_today),
            "fatigue_visuelle": sum(v.posture_time.get("fatigue_visuelle", 0) for v in metrics_today),
        },
        # --- AJOUT DES DONNÉES SAUVEGARDÉES DE FATIGUE ---
        "fatigue_visuelle_data": {
            "perclos": last_session.perclos,
            "blink_rate": last_session.blink_rate_per_min,
            "microsleeps": last_session.microsleep_count,
            "fatigue_score": last_session.visual_fatigue_score
        }
    }

    from vision.cv.medical_rules import detect_symptoms
    symptoms, conditions = detect_symptoms(agg_metrics)

    from vision.cv.llm_service import generate_medical_text
    report_text = generate_medical_text(agg_metrics, symptoms, conditions)

    full_report = {
        "score_posture": score,
        "total_time": agg_metrics["total_time"],
        "mauvaise_posture": agg_metrics["posture_time"],
        "fatigue_visuelle": agg_metrics["fatigue_visuelle_data"], # <-- Injecté dans le JSON retour
        "symptoms": symptoms,
        "conditions": conditions,
        "llm_report": report_text,
        "warning": "⚠️ Ce diagnostic est une estimation..."
    }
    from vision.cv.report_builder import build_full_report

    #return JsonResponse(build_full_report(agg_metrics))
    return JsonResponse(full_report)

   

##################








@csrf_exempt
def reset_metrics(request):
    global blink_counter, blink_consec, blink_state
    global posture_time, last_time, eye_closed_time, total_time
    global last_alert_time, ear_history # <-- Ajout

    blink_counter = 0
    blink_consec = 0
    blink_state = False
    eye_closed_time = 0
    total_time = 0
    posture_time = {
        "tete_penchee": 0,
        "cou_vers_avant": 0,
        "epaules_arrondies": 0,
        "dos_courbe": 0,
        "fatigue_visuelle": 0
    }
    last_time = time.time()
    last_alert_time = time.time()
    ear_history = []

    return JsonResponse({"status": "metrics reset"})



@csrf_exempt
def employee_history(request, employee_id):

     if request.method != "GET":
         return JsonResponse({"message": "Method not allowed"}, status=405)

     uploads = VideoUpload.objects.filter(employee_id=employee_id).order_by("-created_at")

     data = []

     for up in uploads:
         res = VideoAnalysisResult.objects.filter(upload=up).first()

         data.append({
             "id": up.id,
             "date": up.created_at,
             "status": up.status,
             "video": up.video_file.url,
             "score": res.posture_score if res else None,
             "posture_status": res.posture_status if res else None,
             "bad_pct": res.bad_posture_pct if res else None,
         })

     return JsonResponse({"history": data})





@csrf_exempt
def all_employee_history(request):

    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    # ✅ récupérer toutes les vidéos (pas filtrer)
    uploads = VideoUpload.objects.all().order_by("-created_at")
    
    data = []

    for up in uploads:
        res = VideoAnalysisResult.objects.filter(upload=up).first()

        data.append({
            "id": up.id,
            "employee_id": up.employee_id,
            "date": up.created_at,
            "status": up.status,
            "video": up.video_file.url if up.video_file else None,
            "score": res.posture_score if res else None,
            "posture_status": res.posture_status if res else None,
            "bad_pct": res.bad_posture_pct if res else None,
        })

    return JsonResponse({"history": data})

from django.db.models import Avg, Sum, Count
from datetime import timedelta

@csrf_exempt
def vision_history(request, employee_id):
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({"message": "Employee not found"}, status=404)

    sessions = RealtimeMetrics.objects.filter(employee=employee).order_by('created_at')

    if not sessions.exists():
        return JsonResponse({"message": "No data", "history": [], "aggregated": {}})

    # 1. Agrégation globale (KPI du haut)
    total_time = sessions.aggregate(Sum('total_time'))['total_time__sum'] or 0
    avg_fatigue = sessions.aggregate(Avg('visual_fatigue_score'))['visual_fatigue_score__avg'] or 0
    total_microsleeps = sessions.aggregate(Sum('microsleep_count'))['microsleep_count__sum'] or 0
    total_blinks = sessions.aggregate(Sum('blink_count'))['blink_count__sum'] or 0

    posture_totals = {"dos_courbe": 0, "tete_penchee": 0, "cou_vers_avant": 0, "epaules_arrondies": 0}

    # 2. Préparation des données quotidiennes
    daily_data = []
    sessions_by_day = {}

    for session in sessions:
        day_key = session.created_at.date().isoformat()
        if day_key not in sessions_by_day:
            sessions_by_day[day_key] = {
                "date": day_key,
                "fatigue_scores": [],
                "total_time": 0,
                "total_bad_posture_time": 0, # Pour calculer le score %
                "microsleeps": 0,
                "perclos_list": []
            }
        
        # Calcul du temps total de "mauvaise posture" pour cette session spécifique
        # On additionne toutes les postures sauf 'fatigue_visuelle'
        bad_time_session = sum(
            val for key, val in session.posture_time.items() 
            if key != "fatigue_visuelle"
        )

        sessions_by_day[day_key]["total_time"] += session.total_time
        sessions_by_day[day_key]["total_bad_posture_time"] += bad_time_session
        sessions_by_day[day_key]["fatigue_scores"].append(session.visual_fatigue_score)
        sessions_by_day[day_key]["microsleeps"] += session.microsleep_count
        sessions_by_day[day_key]["perclos_list"].append(session.perclos)

        # Remplissage des totaux globaux pour le Pie Chart
        for key in posture_totals.keys():
            posture_totals[key] += session.posture_time.get(key, 0)

    # 3. Calcul final des scores par jour pour l'évolution
    for day_key, day_data in sessions_by_day.items():
        # Formule du score : 100 - (Temps Mauvais / Temps Total * 100)
        if day_data["total_time"] > 0:
            raw_score = 100 - (day_data["total_bad_posture_time"] / day_data["total_time"] * 100)
            avg_posture_score = max(0, round(raw_score, 1))
        else:
            avg_posture_score = 100

        daily_data.append({
            "date": day_key,
            "avg_posture_score": avg_posture_score, # ✅ CRUCIAL pour le graph React
            "avg_fatigue_score": round(sum(day_data["fatigue_scores"]) / len(day_data["fatigue_scores"]), 1),
            "avg_perclos": round(sum(day_data["perclos_list"]) / len(day_data["perclos_list"]), 1),
            "total_time": round(day_data["total_time"], 1),
            "microsleeps": day_data["microsleeps"]
        })

    daily_data.sort(key=lambda x: x["date"])

    return JsonResponse({
        "aggregated": {
            "total_time": round(total_time, 1),
            "avg_fatigue_score": round(avg_fatigue, 1),
            "total_microsleeps": total_microsleeps,
            "total_blinks": total_blinks,
            "posture_totals": posture_totals,
            "first_session": sessions.first().created_at.isoformat(),
            "last_session": sessions.last().created_at.isoformat(),
            "session_count": sessions.count()
        },
        "daily_evolution": daily_data
    })
@csrf_exempt
def all_vision_history(request):
    """
    Retourne l'historique global de TOUS les employés pour l'admin
    """
    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    sessions = RealtimeMetrics.objects.all().order_by('created_at')

    if not sessions.exists():
        return JsonResponse({"message": "No data", "aggregated": {}, "daily_evolution": []})

    # 1. Agrégation globale (KPI)
    total_time = sessions.aggregate(Sum('total_time'))['total_time__sum'] or 0
    avg_fatigue = sessions.aggregate(Avg('visual_fatigue_score'))['visual_fatigue_score__avg'] or 0
    total_microsleeps = sessions.aggregate(Sum('microsleep_count'))['microsleep_count__sum'] or 0

    # 2. Postures globales
    posture_totals = {"dos_courbe": 0, "tete_penchee": 0, "cou_vers_avant": 0, "epaules_arrondies": 0}
    for session in sessions:
        for key in posture_totals.keys():
            posture_totals[key] += session.posture_time.get(key, 0)

    # 3. Évolution quotidienne globale
    daily_data = []
    sessions_by_day = {}
    for session in sessions:
        day_key = session.created_at.date().isoformat()
        if day_key not in sessions_by_day:
            sessions_by_day[day_key] = {"fatigue": [], "total_t": 0, "bad_p": 0, "perclos": []}
        
        sessions_by_day[day_key]["fatigue"].append(session.visual_fatigue_score)
        sessions_by_day[day_key]["total_t"] += session.total_time
        sessions_by_day[day_key]["perclos"].append(session.perclos)
        sessions_by_day[day_key]["bad_p"] += sum(val for k, val in session.posture_time.items() if k != "fatigue_visuelle")

    for day, d in sessions_by_day.items():
        daily_data.append({
            "date": day,
            "avg_fatigue_score": round(sum(d["fatigue"]) / len(d["fatigue"]), 1),
            "avg_perclos": round(sum(d["perclos"]) / len(d["perclos"]), 1),
            "avg_posture_score": round(max(0, 100 - (d["bad_p"] / d["total_t"] * 100)), 1) if d["total_t"] > 0 else 100
        })

    daily_data.sort(key=lambda x: x["date"])

    return JsonResponse({
        "aggregated": {
            "total_time": round(total_time, 1),
            "avg_fatigue_score": round(avg_fatigue, 1),
            "total_microsleeps": total_microsleeps,
            "posture_totals": posture_totals,
            "session_count": sessions.count(),
            "employee_count": sessions.values('employee').distinct().count(),
            "first_session": sessions.first().created_at.isoformat(),
            "last_session": sessions.last().created_at.isoformat(),
        },
        "daily_evolution": daily_data
    })
