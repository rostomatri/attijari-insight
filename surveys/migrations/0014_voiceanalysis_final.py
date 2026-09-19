from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # ✅ Dépend de 0013 (pas de 0011)
        ('surveys', '0013_remove_voiceanalysis_audio_features_and_more'),
    ]

    operations = [
        # Recrée la table complète avec JSONField dès le départ
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS surveys_voiceanalysis;
                
                CREATE TABLE surveys_voiceanalysis (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL,
                    transcript TEXT NOT NULL DEFAULT '',
                    emotion VARCHAR(50) NOT NULL DEFAULT '',
                    emotion_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                    current_skills JSONB NOT NULL DEFAULT '[]',
                    desired_skills JSONB NOT NULL DEFAULT '[]',
                    recommended_position VARCHAR(200) NOT NULL DEFAULT '',
                    match_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    all_recommendations JSONB NOT NULL DEFAULT '[]',
                    validated_positions JSONB NOT NULL DEFAULT '[]',
                    is_sent_to_hr BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS surveys_voiceanalysis;",
        ),
    ]