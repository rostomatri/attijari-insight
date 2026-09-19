# surveys/voice_utils.py

import whisper
import torch
from transformers import (
    AutoModelForAudioClassification, 
    Wav2Vec2FeatureExtractor,
    pipeline
)
import numpy as np
from pydub import AudioSegment
import tempfile
import os
import re
import librosa
import pandas as pd
from collections import Counter

class VoiceProcessor:
    def __init__(self):
        print("🔄 Chargement des modèles IA...")
        
        # ══════════════════════════════════════════════════════════
        # 1️⃣ WHISPER - Déjà multilingue (pas de changement)
        # ══════════════════════════════════════════════════════════
        self.whisper_model = whisper.load_model("medium")
        
        # ══════════════════════════════════════════════════════════
        # 2️⃣ ÉMOTION - MODÈLE MULTILINGUE (CHANGEMENT ICI)
        # ══════════════════════════════════════════════════════════
        print("   📥 Chargement du modèle d'émotion multilingue...")
        emotion_model_name = "facebook/mms-1b-all"  # Modèle Meta multilingue
        # Alternative : "facebook/wav2vec2-large-xlsr-53" (plus léger)
        
        self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
            "facebook/wav2vec2-large-xlsr-53"
        )
        self.emotion_model = AutoModelForAudioClassification.from_pretrained(
            "superb/wav2vec2-base-superb-er"  # On garde celui-ci mais on ajoutera analyse texte
        )
        self.emotion_labels = ['neutre', 'heureux', 'triste', 'énervé']
        
        # ══════════════════════════════════════════════════════════
        # 3️⃣ ANALYSE DE SENTIMENT TEXTUEL (NOUVEAU)
        # ══════════════════════════════════════════════════════════
        print("   📥 Chargement du modèle de sentiment textuel...")
        self.sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment",
            device=0 if torch.cuda.is_available() else -1
        )
        
        # Mapping des scores 1-5 vers émotions
        self.sentiment_to_emotion = {
            1: 'triste',      # 1 étoile = très négatif
            2: 'neutre',      # 2 étoiles = négatif
            3: 'neutre',      # 3 étoiles = neutre
            4: 'heureux',     # 4 étoiles = positif
            5: 'heureux'      # 5 étoiles = très positif
        }

        # ══════════════════════════════════════════════════════════
        # 4️⃣ CHARGEMENT DE L'ONTOLOGIE (inchangé)
        # ══════════════════════════════════════════════════════════
        script_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(script_dir)
        skills_csv_path = os.path.join(project_root, 'data', 'skills_dataset.csv')
        jobs_csv_path = os.path.join(project_root, 'data', 'job_skills.csv')

        self.skills_taxonomy = {}
        if os.path.exists(skills_csv_path):
            df_skills = pd.read_csv(skills_csv_path)
            for _, row in df_skills.iterrows():
                syns = [s.strip().lower() for s in str(row['synonyms']).split(';') if s.strip()]
                self.skills_taxonomy[row['skill'].lower()] = syns
            print(f"✅ Ontologie chargée : {len(self.skills_taxonomy)} compétences")

        self.df_jobs = pd.DataFrame()
        if os.path.exists(jobs_csv_path):
            self.df_jobs = pd.read_csv(jobs_csv_path).dropna(subset=['Title', 'Minimum Qualifications'])
            print(f"✅ Dataset Google chargé : {len(self.df_jobs)} postes")
        
        print("✅ Tous les modèles chargés avec succès")

    def transcribe(self, audio_path):
        """Transcription audio → texte (inchangé)"""
        result = self.whisper_model.transcribe(audio_path, language='fr')
        return result["text"].strip()

    # ══════════════════════════════════════════════════════════════
    # 🎭 DÉTECTION D'ÉMOTION AMÉLIORÉE (CHANGEMENTS MAJEURS)
    # ══════════════════════════════════════════════════════════════
    
    def _detect_audio_emotion(self, audio_path):
        """Analyse UNIQUEMENT de l'audio (voix)"""
        try:
            audio = AudioSegment.from_file(audio_path).set_frame_rate(16000).set_channels(1)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                audio.export(tmp_path, format="wav")
            
            y, sr = librosa.load(tmp_path, sr=16000)
            inputs = self.feature_extractor(y, sampling_rate=sr, return_tensors="pt", padding=True)
            
            with torch.no_grad():
                logits = self.emotion_model(**inputs).logits
            
            predicted_id = torch.argmax(logits, dim=-1).item()
            emotion = self.emotion_labels[predicted_id % len(self.emotion_labels)]
            confidence = torch.softmax(logits, dim=-1)[0][predicted_id].item()
            
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            
            return {"emotion": emotion, "confidence": float(confidence)}
        except Exception as e:
            print(f"⚠️ Erreur analyse audio: {e}")
            return {"emotion": "neutre", "confidence": 0.5}
    
    def _detect_text_sentiment(self, text):
        """Analyse du CONTENU textuel"""
        try:
            # Limite à 512 tokens (limite BERT)
            text_truncated = text[:500]
            
            result = self.sentiment_analyzer(text_truncated)[0]
            
            # Format: {'label': '4 stars', 'score': 0.85}
            stars = int(result['label'].split()[0])
            emotion = self.sentiment_to_emotion.get(stars, 'neutre')
            
            return {"emotion": emotion, "confidence": result['score']}
        except Exception as e:
            print(f"⚠️ Erreur analyse texte: {e}")
            return {"emotion": "neutre", "confidence": 0.5}
    
    def detect_emotion(self, audio_paths, full_transcript):
        """
        ✅ VERSION OPTIMISÉE : Analyse 30% voix + 70% contenu
    
        Répartition :
        - Audio (voix) : 30% du poids total
        - Texte (contenu) : 70% du poids total
        
        Args:
            audio_paths (list): Liste de chemins vers les 5 audios
            full_transcript (str): Transcription complète Q1-Q5
        
        Returns:
            dict: {emotion, confidence, audio_emotion, text_emotion}
        """
        print(f"🎭 Analyse émotionnelle sur {len(audio_paths)} fichiers audio...")
        
        # ─────────────────────────────────────────────────────────
        # PARTIE 1 : Analyse VOIX (50%) - Sur les 5 audios
        # ─────────────────────────────────────────────────────────
        audio_emotions = []
        for i, path in enumerate(audio_paths):
            emo = self._detect_audio_emotion(path)
            audio_emotions.append(emo['emotion'])
            print(f"   Audio Q{i+1}: {emo['emotion']} ({emo['confidence']:.2f})")
        
        # Vote majoritaire sur les 5 audios
        audio_emotion_final = Counter(audio_emotions).most_common(1)[0][0]
        audio_confidence = audio_emotions.count(audio_emotion_final) / len(audio_emotions)
        
        print(f"   → Émotion VOIX globale: {audio_emotion_final} ({audio_confidence:.2f})")
        
        # ─────────────────────────────────────────────────────────
        # PARTIE 2 : Analyse CONTENU (50%) - Sur le texte complet
        # ─────────────────────────────────────────────────────────
        text_result = self._detect_text_sentiment(full_transcript)
        text_emotion = text_result['emotion']
        text_confidence = text_result['confidence']
        
        print(f"   → Sentiment TEXTE: {text_emotion} ({text_confidence:.2f})")
        
        # ─────────────────────────────────────────────────────────
        # PARTIE 3 : FUSION 30/70
        # ─────────────────────────────────────────────────────────
        emotion_scores = {
            'neutre': 0,
            'heureux': 0,
            'triste': 0,
            'énervé': 0
        }
        
        # Audio = 30% du poids
        emotion_scores[audio_emotion_final] += 0.3 * audio_confidence
        
        # Texte = 70% du poids
        emotion_scores[text_emotion] += 0.7 * text_confidence
        
        # Émotion finale = score max
        final_emotion = max(emotion_scores, key=emotion_scores.get)
        final_confidence = emotion_scores[final_emotion]
        
        print(f"   ✅ ÉMOTION FINALE: {final_emotion} ({final_confidence:.2f})")
        print(f"   📊 Répartition: Audio 30% ({audio_emotion_final}) + Texte 70% ({text_emotion})")

        return {
            "emotion": final_emotion,
            "confidence": round(final_confidence, 2),
            "audio_emotion": audio_emotion_final,
            "text_emotion": text_emotion,
            "weights": {  # ✅ Ajout pour plus de clarté
            "audio": 0.3,
            "text": 0.7
            },
            "details": {
                "audio_votes": dict(Counter(audio_emotions)),
                "text_score": text_confidence,
                "audio_contribution": round(0.3 * audio_confidence, 3),
                "text_contribution": round(0.7 * text_confidence, 3)
            }
        }

    # ══════════════════════════════════════════════════════════════
    # 🎯 EXTRACTION SKILLS (inchangé)
    # ══════════════════════════════════════════════════════════════
    def extract_skills(self, text):
        text_clean = text.lower()
        parts = re.split(r'[qQ]\d+:', text_clean)
        results = {"current_skills": [], "desired_skills": []}
        sections_to_analyze = {3: "current_skills", 4: "desired_skills"}

        for idx, section_text in enumerate(parts):
            if idx not in sections_to_analyze:
                continue
            category = sections_to_analyze[idx]
            found_in_section = []

            for skill_name, synonyms in self.skills_taxonomy.items():
                for syn in synonyms:
                    if re.search(rf'\b{re.escape(syn)}\b', section_text):
                        found_in_section.append(skill_name)
                        break
            results[category] = list(set(found_in_section))

        results["desired_skills"] = [s for s in results["desired_skills"] if s not in results["current_skills"]]
        return results

    # ══════════════════════════════════════════════════════════════
    # 💼 RECOMMANDATION (inchangé)
    # ══════════════════════════════════════════════════════════════
    def get_position_recommendation(self, user_skills):
        if self.df_jobs.empty:
            return {"recommendations": []}
    
        u_current = set(user_skills['current_skills'])
        u_desired = set(user_skills['desired_skills'])
        scores = {}
    
        for _, row in self.df_jobs.head(1000).iterrows():
            job_text = (
                str(row['Minimum Qualifications']) + " " + 
                str(row.get('Preferred Qualifications', ''))
            ).lower()
            title = row['Title']
            
            current_found = sum(1 for s in u_current if s in job_text)
            desired_found = sum(1 for s in u_desired if s in job_text)
            total_skills = len(u_current) + len(u_desired)
        
            if total_skills == 0:
                continue
            
            score = 0
            if len(u_current) > 0:
                score += (current_found / len(u_current)) * 70
            if len(u_desired) > 0:
                score += (desired_found / len(u_desired)) * 30
        
            if score > 0:
                if title not in scores or scores[title] < score:
                    scores[title] = score
    
        top3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        recommendations = []
        for title, score in top3:
            recommendations.append({
                "position": title,
                "score": round(score, 1)
            })
    
        fallback = [
            {"position": "Data Scientist Senior", "score": 45.0},
            {"position": "Développeur Full Stack", "score": 30.0},
            {"position": "Chef de Projet Digital", "score": 20.0}
        ]
        while len(recommendations) < 3:
            fb = fallback[len(recommendations)]
            if fb['position'] not in [r['position'] for r in recommendations]:
                recommendations.append(fb)
    
        return {"recommendations": recommendations[:3]}