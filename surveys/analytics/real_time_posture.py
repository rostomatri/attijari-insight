#  test

import cv2
import mediapipe as mp
import math

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def analyze_posture_frame(frame, pose):
    """
    Analyse une frame et retourne :
    - torso_angle : angle du torse en degrés
    - shoulder_asym : asymétrie des épaules (0 = symétrique, 1 = max)
    """
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(frame_rgb)

    torso_angle = 0
    shoulder_asym = 0

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark

        # Keypoints des épaules et hanches
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]

        # Angle du torse = angle entre la ligne épaules → hanches et la verticale
        mid_shoulder_x = (left_shoulder.x + right_shoulder.x) / 2
        mid_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        mid_hip_x = (left_hip.x + right_hip.x) / 2
        mid_hip_y = (left_hip.y + right_hip.y) / 2

        dx = mid_hip_x - mid_shoulder_x
        dy = mid_hip_y - mid_shoulder_y
        torso_angle = abs(math.degrees(math.atan2(dy, dx)) - 90)  # 0 = droit, plus = penché

        # Asymétrie des épaules = différence horizontale normalisée
        shoulder_asym = abs(left_shoulder.x - right_shoulder.x)

        # Tracer les points et lignes pour visualisation
        h, w, _ = frame.shape
        cv2.circle(frame, (int(left_shoulder.x * w), int(left_shoulder.y * h)), 5, (0,0,255), -1)
        cv2.circle(frame, (int(right_shoulder.x * w), int(right_shoulder.y * h)), 5, (0,0,255), -1)
        cv2.circle(frame, (int(mid_shoulder_x * w), int(mid_shoulder_y * h)), 5, (255,0,0), -1)
        cv2.circle(frame, (int(mid_hip_x * w), int(mid_hip_y * h)), 5, (255,0,0), -1)
        cv2.line(frame, (int(mid_shoulder_x * w), int(mid_shoulder_y * h)),
                 (int(mid_hip_x * w), int(mid_hip_y * h)), (0,255,0), 2)

    return torso_angle, shoulder_asym, frame

def real_time_posture():
    """
    Capture la vidéo webcam et affiche le torse et l'asymétrie en temps réel
    """
    cap = cv2.VideoCapture(0)

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            torso_angle, shoulder_asym, annotated_frame = analyze_posture_frame(frame, pose)

            cv2.putText(annotated_frame, f"Torso angle: {torso_angle:.1f}", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
            cv2.putText(annotated_frame, f"Shoulder asym: {shoulder_asym:.2f}", (10,60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

            cv2.imshow("Posture Real-Time", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()








if __name__ == "__main__":
    real_time_posture()