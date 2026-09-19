def detect_symptoms(metrics):
    posture_time = metrics.get("posture_time", {})
    # Récupération sécurisée des nouvelles données de fatigue visuelle
    fatigue_data = metrics.get("fatigue_visuelle_data", {})

    symptoms = []
    conditions = []

    # --- RÈGLES POSTURALES EXISTANTES ---
    if posture_time.get("dos_courbe", 0) > 60:
        symptoms.append("Tension dorsale prolongée")
        conditions.append("tension_dorsale")

    if posture_time.get("tete_penchee", 0) > 60:
        symptoms.append("Inclinaison excessive de la tête")
        conditions.append("probleme_cervical")

    if posture_time.get("cou_vers_avant", 0) > 60:
        symptoms.append("Cou projeté vers l’avant")
        conditions.append("syndrome_cou")

    # --- NOUVELLES RÈGLES : FATIGUE VISUELLE ---
    perclos = fatigue_data.get("perclos", 0)
    blink_rate = fatigue_data.get("blink_rate", 0)
    microsleeps = fatigue_data.get("microsleeps", 0)

    # 1. PERCLOS Élevé (Paupières lourdes)
    if perclos > 10:
        symptoms.append(f"Fermeture prolongée des paupières (PERCLOS : {round(perclos, 1)}%)")
        conditions.append("fatigue_oculaire_severe")

    # 2. Détection de Micro-sommeils (Danger critique)
    if microsleeps > 0:
        symptoms.append(f"Épisodes de somnolence ({microsleeps} micro-sommeils détectés)")
        conditions.append("somnolence_critique")

    # 3. Fréquence de clignement anormale
    if 0 < blink_rate < 10:
        symptoms.append("Fixation oculaire excessive (taux de clignements très faible)")
        conditions.append("secheresse_oculaire")
    elif blink_rate > 25:
        symptoms.append("Clignements excessifs (signe d'irritation ou spasmes)")
        conditions.append("irritation_oculaire")

    return symptoms, conditions