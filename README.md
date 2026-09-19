<div align="center">

<img src="https://img.shields.io/badge/Status-Completed%20PFE-brightgreen?style=for-the-badge" />
<img src="https://img.shields.io/badge/Duration-6%20Months-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/Partner-Attijari%20Bank%20Tunisia-orange?style=for-the-badge" />

# 🧠 Attijari Insight
### Système Intelligent IA pour le Bien-Être et la Performance des employés en Banque

> **Projet de Fin d'Études (PFE) — 6 mois | Attijari Bank Tunisie**  
> Plateforme Full Stack intégrant Computer Vision, Analyse Vocale et NLP pour le suivi automatisé du bien-être des employés bancaires.

</div>

---

## 📌 Table des Matières

- [Vue d'ensemble](#-vue-densemble)
- [Architecture Technique](#️-architecture-technique)
- [Modules IA](#-modules-ia)
  - [Module 1 — Analyse Comportementale (Computer Vision)](#-module-1--analyse-comportementale-computer-vision)
  - [Module 2 — Analyse Vocale & Sentiment](#-module-2--analyse-vocale--sentiment)
  - [Module 3 — Questionnaire Adaptatif Intelligent](#-module-3--questionnaire-adaptatif-intelligent)
- [Stack Technologique](#-stack-technologique)
- [Fonctionnalités Clés](#-fonctionnalités-clés)
- [Structure du Projet](#-structure-du-projet)
- [Installation & Lancement](#-installation--lancement)
- [Aperçu des Dashboards](#-aperçu-des-dashboards)
- [Contact](#-contact)

---

## 🎯 Vue d'ensemble

**Attijari Insight** est une plateforme web intelligente développée dans le cadre d'un Projet de Fin d'Études de 6 mois au sein d'**Attijari Bank Tunisie**. Elle répond à une problématique RH réelle : **comment monitorer objectivement le bien-être et la performance des employés sans surcharger les équipes RH**, grâce à l'automatisation par l'Intelligence Artificielle.

### Problématique
Les banques gèrent des équipes soumises à une forte pression cognitive. Les signaux de fatigue, de désengagement ou de mal-être passent souvent inaperçus jusqu'à ce qu'ils impactent la performance ou la santé des employés.

### Solution
Une plateforme **non-intrusive, personnalisée et automatisée** articulée autour de **3 modules IA complémentaires** qui collectent, analysent et restituent des insights actionnables aux employés et aux administrateurs RH.

---

## 🏗️ Architecture Technique

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React.js)                       │
│           Dashboard Employé │ Dashboard Admin │ Modules IA       │
│                    Visualisations : Recharts                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │  REST API
┌─────────────────────▼───────────────────────────────────────────┐
│                       BACKEND (Django)                           │
│   Computer Vision │ Voice Analysis │ Questionnaire │ Auth/RH     │
│            Cache : Redis │ Base de données : PostgreSQL          │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼────────────────────────────┐
│   COUCHE IA / ML    │  │         SERVICES EXTERNES            │
│ MediaPipe │ Whisper │  │  Gemini API │ Grok API               │
│ Wav2Vec2  │ BERT    │  │  (Diagnostics & Génération NLP)      │
│ scikit-learn│ NLTK  │  └─────────────────────────────────────┘
└─────────────────────┘
```

---

## 🤖 Modules IA

### 👁️ Module 1 — Analyse Comportementale (Computer Vision)

> *L'employé active sa caméra et bénéficie d'un suivi en temps réel, non-intrusif.*

#### Analyse de Fatigue Visuelle (MediaPipe Face Mesh)
| Métrique | Description |
|---|---|
| **EAR** (Eye Aspect Ratio) | Ratio d'ouverture des yeux pour détecter la somnolence |
| **PERCLOS** | % de temps où les yeux sont fermés sur une fenêtre glissante |
| **Fréquence de clignement** | Nombre de clignements/minute (norme : 15-20/min) |
| **Alertes** | Déclenchement automatique en cas de somnolence ou micro-sommeil |

**Visualisations temps réel :**
- Courbe d'ouverture des yeux en direct
- Score de fatigue dynamique
- Indice PERCLOS avec seuils critiques

#### Analyse Posturale (MediaPipe Pose)
- Score de bonne/mauvaise posture en temps réel (%)
- Détection des déviations posturales
- Suivi longitudinal sur la journée

#### Diagnostic Personnalisé (Gemini API)
- Génère un diagnostic journalier basé sur les métriques comportementales
- Recommandations personnalisées à l'employé selon son profil du jour
- Stockage optimisé via **cache Redis**

---

### 🎙️ Module 2 — Analyse Vocale & Sentiment

> *Une session de questions-réponses vocales pour un état des lieux humain et automatisé.*

#### Questions posées à l'employé
- Comment vous sentez-vous aujourd'hui ?
- Qu'est-ce qui vous plaît dans votre travail ?
- Quelles compétences exercez-vous aujourd'hui ?
- Quelles compétences souhaiteriez-vous développer davantage ?
- Quelles sont vos attentes actuelles ?

#### Pipeline d'Analyse

```
Audio de l'employé
       │
       ├──► Transcription (OpenAI Whisper) ──► Extraction de compétences
       │
       ├──► Analyse paraverbale (texte transcrit)
       │         Wav2Vec2 ──► Sentiment textuel
       │
       └──► Analyse prosodique (voix brute)
                 BERT Multilingual ──► Sentiment vocal
                         │
                         ▼
              Fusion 50% / 50% ──► État émotionnel final
              (Énervé / Heureux / Neutre / Fatigué / ...)
```

#### Recommandation de Compétences
- Algorithme basé sur **pandas + scikit-learn**
- Propose **3 formations/compétences** adaptées au profil détecté
- L'employé valide et choisit d'envoyer ou non à l'équipe RH

---

### 📋 Module 3 — Questionnaire Adaptatif Intelligent

> *Pour les employés ne souhaitant pas activer la caméra — une alternative textuelle intelligente.*

| Composant | Technologie | Rôle |
|---|---|---|
| Génération de questions | **Grok API + NLP** | Questions dynamiques adaptées au profil employé |
| Classification | **K-Means** | Regroupement des suggestions et thématiques |
| Personnalisation | Profil historique | Questionnaire unique à chaque employé |
| Automatisation RH | Pipeline complet | Zéro intervention humaine requise |

**Avantage clé :** Remplace les enquêtes RH manuelles périodiques par un système continu, automatisé et personnalisé.

---

## 💻 Stack Technologique

### Backend
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)

### Frontend
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![Recharts](https://img.shields.io/badge/Recharts-22B5BF?style=flat)

### Intelligence Artificielle & ML
![MediaPipe](https://img.shields.io/badge/MediaPipe-0097A7?style=flat&logo=google&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat&logo=scikit-learn&logoColor=white)

| Domaine | Modèle/Lib |
|---|---|
| Computer Vision | MediaPipe Face Mesh + Pose |
| Speech-to-Text | OpenAI Whisper |
| Analyse sentimentale vocale | Wav2Vec2 |
| Analyse sentimentale textuelle | BERT Multilingual |
| Diagnostic IA | Google Gemini API |
| Questionnaire adaptatif | Grok API + NLP |
| Clustering | K-Means (scikit-learn) |
| Recommandation | Pandas + scikit-learn |

---

## ✨ Fonctionnalités Clés

- 🔴 **Temps réel** — Analyse comportementale en streaming avec alertes instantanées
- 🧩 **3 modules complémentaires** — Camera / Vocal / Questionnaire (au choix de l'employé)
- 🔒 **Non-intrusif** — L'employé contrôle ce qu'il active
- 📊 **Dashboards complets** — Vue employé + vue administrateur RH
- 🤖 **100% automatisé** — Aucune intervention RH requise pour le suivi quotidien
- 🌍 **Multilingue** — BERT Multilingual pour l'analyse en français/arabe
- ⚡ **Performant** — Cache Redis pour les diagnostics répétitifs

---

## 📁 Structure du Projet

```
attijari-insight/
│
├── src/                        # Backend Django
│   ├── behavioral/             # Module Computer Vision (MediaPipe)
│   ├── voice/                  # Module Analyse Vocale (Whisper, Wav2Vec2, BERT)
│   ├── surveys/                # Module Questionnaire adaptatif
│   ├── dashboard/              # API Dashboard employé & admin
│   ├── recommendations/        # Moteur de recommandation compétences
│   └── core/                   # Auth, modèles de base, config
│
├── frontend/                   # Application React.js
│   ├── src/
│   │   ├── components/         # Composants réutilisables
│   │   ├── pages/              # Pages principales (Dashboard, Modules)
│   │   └── charts/             # Visualisations Recharts
│   └── package.json
│
├── surveys/                    # Logique métier questionnaires
├── manage.py                   # Point d'entrée Django
├── requirements.txt            # Dépendances Python (vision + core)
├── requirements_voice.txt      # Dépendances Python (audio/NLP)
├── package.json                # Dépendances Node.js
├── .env.example                # Template variables d'environnement
└── README.md
```

---

## 🚀 Installation & Lancement

### Prérequis
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis

### Backend (Django)

```bash
# Cloner le projet
git clone https://github.com/votre-username/attijari-insight.git
cd attijari-insight

# Environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dépendances
pip install -r requirements.txt
pip install -r requirements_voice.txt

# Variables d'environnement
cp .env.example .env
# Remplir .env avec vos clés API (Gemini, Grok, DB credentials)

# Base de données
python manage.py migrate

# Lancer le serveur
python manage.py runserver
```

### Frontend (React.js)

```bash
cd frontend
npm install
npm start
```

### Variables d'environnement requises (`.env`)

```env
# Base de données
DATABASE_URL=postgresql://user:password@localhost:5432/attijari_insight

# Cache
REDIS_URL=redis://localhost:6379

# APIs IA
GEMINI_API_KEY=your_gemini_api_key
GROK_API_KEY=your_grok_api_key

# Django
SECRET_KEY=your_django_secret_key
DEBUG=False
```

---

## 📊 Aperçu des Dashboards

### Dashboard Employé
- Vue synthétique de son état du jour (fatigue, sentiment, posture)
- Historique de ses sessions comportementales
- Recommandations de compétences reçues
- Questionnaires adaptatifs à compléter

### Dashboard Administrateur (RH)
- Vue globale de l'équipe avec agrégats anonymisés
- Alertes de bien-être à traiter
- Suivi des recommandations de compétences envoyées
- Statistiques par département / période

---

## 👤 Contact

**Rostom Atri** — Jeune diplômée en Data Science | PFE Attijari Bank Tunisie

[![LinkedIn](https://linkedin.com/in/rostom-atri )


---

<div align="center">

**⭐ N'hésitez pas à star ce projet s'il vous a été utile !**

*Projet réalisé dans le cadre du PFE — [Esprit] × Attijari Bank Tunisie — 2024/2025*

</div>
