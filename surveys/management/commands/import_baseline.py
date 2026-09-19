# surveys/management/commands/import_baseline.py

import os
import json
import hashlib
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from surveys.models import Employee, Survey, SurveyResponse, Question, Answer

# ✅ keys attendues dans la BD (Question.key)
KEYS = [
    "stress_level",
    "mental_fatigue",
    "workload",
    "sleep_quality",
    "job_satisfaction",
    "recognition",
    "motivation",
    "concentration_difficulty",
    "suggestions",
]

# ✅ Si ton fichier a des colonnes "longues" (comme ton CSV original),
# tu peux garder ton COL_MAP (copié de baseline_nlp.py)
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


def _hash_email(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Importe un fichier (CSV/JSON) de réponses baseline dans Postgres (Employee/SurveyResponse/Answer)."

    def add_arguments(self, parser):
        parser.add_argument("--survey_id", type=int, required=True, help="ID du Survey cible.")
        parser.add_argument("--path", type=str, required=True, help="Chemin du fichier CSV ou JSON.")
        parser.add_argument("--format", type=str, choices=["csv", "json"], default="csv", help="Format du fichier.")
        parser.add_argument("--use_col_map", action="store_true", help="Appliquer COL_MAP (colonnes longues -> keys).")
        parser.add_argument("--create_questions", action="store_true", help="Créer les Questions manquantes automatiquement.")
        parser.add_argument("--batch", type=int, default=500, help="Taille de batch commit (par défaut 500).")

    def handle(self, *args, **opts):
        survey_id = opts["survey_id"]
        path = opts["path"]
        fmt = opts["format"]
        use_col_map = opts["use_col_map"]
        create_questions = opts["create_questions"]
        batch_size = int(opts["batch"])

        if not os.path.exists(path):
            raise CommandError(f"Fichier introuvable: {path}")

        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            raise CommandError(f"Survey introuvable (id={survey_id})")

        # 1) Charger données
        if fmt == "csv":
            df = pd.read_csv(path)
        else:
            # JSON: accepte soit une liste d'objets, soit un dict avec "data"
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict) and "data" in obj:
                obj = obj["data"]
            if not isinstance(obj, list):
                raise CommandError("JSON invalide: attendu une liste d'objets (rows).")
            df = pd.DataFrame(obj)

        if use_col_map:
            df = df.rename(columns=COL_MAP)

        # 2) Vérifier colonnes minimales
        missing = [k for k in KEYS if k not in df.columns]
        if missing:
            # on les crée vides pour éviter crash
            for k in missing:
                df[k] = ""

        # 3) Préparer Questions
        existing_qs = Question.objects.filter(survey=survey).all()
        q_by_key = {q.key: q for q in existing_qs}

        if create_questions:
            created_count = 0
            order = 0
            for k in KEYS:
                if k not in q_by_key:
                    q = Question.objects.create(
                        survey=survey,
                        key=k,
                        text=k,  # tu peux remplacer par le vrai texte si tu veux
                        question_type="text",
                        is_required=False,
                        order=order,
                    )
                    q_by_key[k] = q
                    created_count += 1
                order += 1
            self.stdout.write(self.style.SUCCESS(f"Questions créées: {created_count}"))
        else:
            # si on ne crée pas, on warn
            for k in KEYS:
                if k not in q_by_key:
                    self.stdout.write(self.style.WARNING(f"Question manquante en BD pour key='{k}' (elle sera ignorée)."))

        # 4) Import rows -> Employee + SurveyResponse + Answer
        n = len(df)
        if n == 0:
            self.stdout.write(self.style.WARNING("Aucune ligne à importer."))
            return

        self.stdout.write(f"Import de {n} réponses vers survey_id={survey_id} ...")

        imported = 0
        skipped = 0

        # Cache local pour réduire hits BD (email_hash -> Employee)
        employee_cache = {}

        # Pour éviter conflit uniq_employee_survey, on crée UN employé par ligne.
        # Si tu veux autre logique (email venant du fichier), dis-moi.
        def get_or_create_employee(i: int) -> Employee:
            email = f"imported_{survey_id}_{i}@baseline.local"
            h = _hash_email(email)

            emp = employee_cache.get(h)
            if emp:
                return emp

            emp = Employee.objects.filter(email_hash=h).first()
            if not emp:
                emp = Employee.objects.create(
                    email_hash=h,
                    password_hash=None,
                    department="",
                    role="",
                    seniority="",
                    work_mode="",
                    is_admin=False,
                    is_profile_completed=False,
                )
            employee_cache[h] = emp
            return emp

        # Batches
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)

            with transaction.atomic():
                for i in range(start, end):
                    row = df.iloc[i]

                    # employé unique par ligne
                    emp = get_or_create_employee(i)

                    # create SurveyResponse (pas update_or_create, car employé unique)
                    sr, _ = SurveyResponse.objects.update_or_create(
                        employee=emp,
                        survey=survey,
                        defaults={"submitted_at": timezone.now()},
                    )

                    # answers
                    for k in KEYS:
                        q = q_by_key.get(k)
                        if not q:
                            continue
                        val = row.get(k, "")
                        if pd.isna(val):
                            val = ""
                        Answer.objects.update_or_create(
                            response=sr,
                            question=q,
                            defaults={"value": str(val)},
                        )

                    imported += 1

            self.stdout.write(f"Batch {start}-{end} OK (imported={imported})")

        self.stdout.write(self.style.SUCCESS(f"✅ Import terminé: {imported} réponses importées."))

        self.stdout.write(self.style.SUCCESS(
            "👉 Prochaine étape: lance rebuild analytics (ou appelle ton endpoint save pour auto-update)."
        ))