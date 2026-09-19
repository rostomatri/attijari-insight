from openai import OpenAI
from datetime import datetime

# ⚠️ Configuration du client Gemini via l'API OpenAI-compatible
client = OpenAI(
    api_key="AIzaSyAHMsY51UxfWFh92hmf0nxOT7PIHSLg0Ac",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def generate_medical_text(metrics, symptoms, conditions):
    today = datetime.now().strftime("%d %B %Y")
    
    # Récupération sécurisée des métriques visuelles
    fatigue_data = metrics.get("fatigue_visuelle_data", {})
    fatigue_score = fatigue_data.get("fatigue_score", 0)
    perclos = fatigue_data.get("perclos", 0)
    blink_rate = fatigue_data.get("blink_rate", 0)
    microsleeps = fatigue_data.get("microsleeps", 0)

    prompt = f"""
Tu es un médecin spécialiste en ergonomie, santé au travail et ophtalmologie.
📅 Date : {today}

📊 Données biométriques du patient :
- Durée analysée : {metrics.get('total_time', 0)} secondes
- Score posture : {metrics.get('score', 0)}%
- Temps dos courbé : {metrics.get('posture_time', {}).get('dos_courbe', 0)} sec
- Temps tête penchée : {metrics.get('posture_time', {}).get('tete_penchee', 0)} sec
- Temps cou vers avant : {metrics.get('posture_time', {}).get('cou_vers_avant', 0)} sec

👁️ Données de Fatigue Visuelle (EAR) :
- Score de fatigue oculaire : {fatigue_score}/100 (0=Reposé, 100=Épuisé)
- Indice PERCLOS : {perclos}% (Norme médicale < 5%)
- Fréquence de clignements : {blink_rate} /min (Norme : 15 à 20)
- Micro-sommeils détectés (>2s yeux fermés) : {microsleeps}

🧠 Symptômes cliniques détectés par l'IA :
{", ".join(symptoms) if symptoms else "Aucun symptôme critique"}

🩺 Troubles ou pathologies possibles :
{", ".join(conditions) if conditions else "Aucun trouble majeur"}

Génère un rapport MÉDICAL COURT et STRUCTURÉ comme une fiche clinique réelle.
Si des données de fatigue visuelle sont anormales, INCLUS des explications ophtalmologiques et des recommandations adaptées (règle des 20-20-20, hydratation oculaire, etc.).

Format OBLIGATOIRE :

🧾 Synthèse clinique :
(3-4 lignes max, résumé global posture + vision)

⚠️ Points critiques :
(Symptômes ressentis, douleurs, fatigue visuelle ou somnolence)

 Explication :
(3-4 lignes simples de biomécanique et physiologie oculaire)

📉 Risques :
(3-4 risques max à long terme, ex: TMS, syndrome de l'œil sec)

💊 Recommandations :
(3-5 actions concrètes, ergonomiques et visuelles)

Contraintes :
- court et très professionnel
- phrases simples et directes
- pas de long paragraphe
"""

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    return response.choices[0].message.content