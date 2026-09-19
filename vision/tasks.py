from celery import shared_task
from .models import VideoUpload, VideoAnalysisResult, VideoSegment
from .models import RealtimeMetrics
from .cv.pipeline import run_cv_pipeline
from surveys.models import PostureMetric
@shared_task
def analyze_video(upload_id: int): 
    print(f"🚀 START TASK analyze_video for upload_id={upload_id}") 
    upload = VideoUpload.objects.get(id=upload_id) 
    print(f"Upload found: {upload}") 
    upload.status = "PROCESSING" 
    upload.save(update_fields=["status"]) 
    
    try: 
        out = run_cv_pipeline(upload.video_file.path, fps_used=upload.fps_used) 
        print("DEBUG RUN_CV_PIPELINE OUTPUT:", out) 
        if not out: 
            raise ValueError("run_cv_pipeline returned None or empty dict") 
        upload.duration_sec = out.get("duration_sec") 
        upload.save(update_fields=["duration_sec"]) 
        
        VideoAnalysisResult.objects.update_or_create( 
            upload=upload, 
            defaults={ 
                "posture_score": out["posture_score"], 
                "posture_status": out["posture_status"], 
                "bad_posture_pct": out["bad_posture_pct"], 
                "summary_text": "Analyse posture terminée.", 
                } 
                ) 
        # segments 
        VideoSegment.objects.filter(upload=upload).delete() 
        for s in out["segments"]: 
            VideoSegment.objects.create( 
                upload=upload, 
                type=s["type"], 
                start_sec=s["start_sec"], 
                end_sec=s["end_sec"], 
                severity=s.get("severity", 3), 
                meta=s.get("meta", {}), 
            ) 
        upload.status = "DONE" 
        upload.save(update_fields=["status"]) 
        metrics = out # 🔥 important 
        print("🚀 AVANT CREATE METRICS") 
        PostureMetric.objects.create( 
            employee=upload.employee, 
            total_time=metrics.get("total_time", 0), 
            eye_closed_time=metrics.get("eye_closed_time", 0), 
            blink_count=metrics.get("blink_count", 0), 
            tete_penchee_time=metrics.get("posture_time", {}).get("tete_penchee", 0), 
            cou_vers_avant_time=metrics.get("posture_time", {}).get("cou_vers_avant", 0), 
            epaules_arrondies_time=metrics.get("posture_time", {}).get("epaules_arrondies", 0), 
            dos_courbe_time=metrics.get("posture_time", {}).get("dos_courbe", 0), 
            fatigue_visuelle_time=metrics.get("posture_time", {}).get("fatigue_visuelle", 0), 
            score=metrics.get("posture_score", 100), 
            video_file=upload.video_file 
        ) 
        print("OUT PIPELINE =", out) 
        print("✅ METRICS SAVED") 

    except Exception as e: 
        upload.status = "FAILED" 
        upload.error_message = str(e) 
        upload.save(update_fields=["status", "error_message"]) 
        raise

# @shared_task
# def visualize_posture_task(result_json):
#     """
#     Appelle le script de visualisation pour la dernière vidéo uploadée
#     """
#     plot_posture_from_json(result_json)

    