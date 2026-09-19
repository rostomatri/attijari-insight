import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder
# ===============================
# 1) Charger dataset (chemin dynamique)
# ===============================
BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "..", "..", "data", "Employee_Attrition.csv")

df = pd.read_csv(file_path)

print("\n===== APERÇU DES DONNÉES =====")
print(df.head())

print("\n===== INFORMATIONS DATASET =====")
print(df.info())

print("\n===== TAILLE DATASET =====")
print(df.shape)

print("\n===== NOMS DES COLONNES =====")
print(df.columns)

# ===============================
# 2) Valeurs manquantes (avant)
# ===============================
print("\n===== VALEURS MANQUANTES (AVANT) =====")
missing_before = df.isnull().sum()
print(missing_before)

print("\n% valeurs manquantes (avant) :")
print((missing_before / len(df)) * 100)

# ===============================
# 3) Suppression des NaN (≈5%)
# ===============================
print("\n===== SUPPRESSION DES VALEURS MANQUANTES =====")
before = df.shape
df = df.dropna()
after = df.shape

print(f"Lignes avant suppression : {before}")
print(f"Lignes après suppression : {after}")
print(f"Lignes supprimées : {before[0] - after[0]}")

print("\nVérification NaN restants :")
missing_after = df.isnull().sum()
print(missing_after)

print("\n% valeurs manquantes (après) :")
print((missing_after / len(df)) * 100)

# ===============================
# 4) Statistiques
# ===============================
print("\n===== STATISTIQUES NUMÉRIQUES =====")
print(df.describe())

print("\n===== STATISTIQUES CATÉGORIELLES =====")
print(df.describe(include=["object", "string"]))
# ===============================
#  Diagrammes catégoriels
# ===============================
plt.figure(figsize=(12, 5))

plt.subplot(1, 2, 1)
sns.countplot(x="dept", data=df)
plt.title("Distribution par département")
plt.xticks(rotation=45)

plt.subplot(1, 2, 2)
sns.countplot(x="salary", data=df)
plt.title("Distribution des salaires")

plt.tight_layout()
plt.show()
# ===============================
# 5) Outliers (IQR)
# ===============================
# VISUALISATION DES OUTLIERS
# ===============================

print("\n===== VISUALISATION DES OUTLIERS =====")

continuous_cols = [
    "satisfaction_level",
    "last_evaluation",
    "number_project",
    "average_montly_hours",
    "time_spend_company"
]

plt.figure(figsize=(14, 8))

for i, col in enumerate(continuous_cols):
    plt.subplot(2, 3, i + 1)
    sns.boxplot(y=df[col])
    plt.title(col)

plt.tight_layout()
plt.show()

# ===============================
# print("\n===== DÉTECTION / SUPPRESSION DES OUTLIERS (IQR) =====")

# # Colonnes numériques (on exclut Emp ID car c’est un identifiant)
# num_cols = df.select_dtypes(include=["number"]).columns.tolist()
# if "Emp ID" in num_cols:
#     num_cols.remove("Emp ID")

# def remove_outliers_iqr(data, cols):
#     filtered = data.copy()
#     for col in cols:
#         Q1 = filtered[col].quantile(0.25)
#         Q3 = filtered[col].quantile(0.75)
#         IQR = Q3 - Q1
#         lower = Q1 - 1.5 * IQR
#         upper = Q3 + 1.5 * IQR

#         before_rows = filtered.shape[0]
#         filtered = filtered[(filtered[col] >= lower) & (filtered[col] <= upper)]
#         removed = before_rows - filtered.shape[0]
#         print(f"- {col}: supprimés {removed} outliers")

#     return filtered

# before_out = df.shape
# df = remove_outliers_iqr(df, num_cols)
# after_out = df.shape

# print("\n✅ Outliers supprimés")
# print("Taille avant :", before_out)
# print("Taille après :", after_out)

# ===============================
# 6) Corrélation (numériques seulement)
# ===============================
print("\n===== MATRICE DE CORRÉLATION (NUMÉRIQUE) =====")
numeric_df = df.select_dtypes(include=["number"])
corr_num = numeric_df.corr()

print(corr_num)

plt.figure(figsize=(10, 8))
sns.heatmap(corr_num, annot=True, cmap="coolwarm", fmt=".2f")
plt.title("Matrice de corrélation (variables numériques)")
plt.tight_layout()
plt.show()

# ===============================
# 7) Corrélation avec catégories encodées
# ===============================
print("\n===== CORRÉLATION (AVEC ENCODAGE dept + salary) =====")

df_encoded = df.copy()
for col in ["dept", "salary"]:
    df_encoded[col] = LabelEncoder().fit_transform(df_encoded[col].astype(str))

corr_all = df_encoded.corr()

plt.figure(figsize=(12, 10))
sns.heatmap(corr_all, annot=True, cmap="coolwarm", fmt=".2f")
plt.title("Matrice de corrélation (avec encodage catégoriel)")
plt.tight_layout()
plt.show()
# ## 
# # #### whisker boxplot 
# # ##
# plt.figure(figsize=(14, 8))
# sns.boxplot(data=df[continuous_cols])
# plt.title("Whisker Boxplot – Outliers")
# plt.show()

# ===============================
# 8) Distributions
# ===============================
print("\n===== DISTRIBUTIONS NUMÉRIQUES =====")
numeric_df.hist(figsize=(12, 10))
plt.suptitle("Distribution des variables numériques", y=1.02)
plt.tight_layout()
plt.show()

print("\n✅ Analyse terminée Employee_Attrition !")
##############
BASE_DIR2 = os.path.dirname(__file__)
file_path2 = os.path.join(BASE_DIR2, "..", "..", "data", "post_pandemic_remote_work_health_impact_2025.csv")


##############
df2 = pd.read_csv(file_path2)
print("\n===== APERÇU DES DONNÉES =====")
print(df2.head())

print("\n===== INFOS DATASET =====")
print(df2.info())

print("\n===== TAILLE DATASET =====")
print(df2.shape)

print("\n===== COLONNES =====")
print(df2.columns)

# ===============================
# 2) Valeurs manquantes
# ===============================
print("\n===== VALEURS MANQUANTES =====")
missing2 = df2.isnull().sum()
print(missing2)

print("\n% valeurs manquantes :")
print((missing2 / len(df2)) * 100)

# ===============================
# IMPUTATION DES VALEURS MANQUANTES (ROBUSTE)
# ===============================

print("\n===== IMPUTATION DES VALEURS MANQUANTES =====")

df_imputed = df2.copy()

for col in df_imputed.columns:
    if df_imputed[col].isnull().sum() == 0:
        continue

    # ✅ Si la colonne est catégorielle (object / string / category / bool)
    if pd.api.types.is_object_dtype(df_imputed[col]) or \
       pd.api.types.is_string_dtype(df_imputed[col]) or \
       pd.api.types.is_categorical_dtype(df_imputed[col]) or \
       pd.api.types.is_bool_dtype(df_imputed[col]):

        mode_val = df_imputed[col].mode(dropna=True)[0]
        df_imputed[col] = df_imputed[col].fillna(mode_val)
        print(f"{col} → imputé avec MODE : {mode_val}")

    # ✅ Sinon (numérique)
    elif pd.api.types.is_numeric_dtype(df_imputed[col]):
        median_val = df_imputed[col].median()
        df_imputed[col] = df_imputed[col].fillna(median_val)
        print(f"{col} → imputé avec MEDIAN : {median_val}")

    else:
        # fallback (rare)
        mode_val = df_imputed[col].mode(dropna=True)[0]
        df_imputed[col] = df_imputed[col].fillna(mode_val)
        print(f"{col} → imputé (fallback) avec MODE : {mode_val}")

print("\nNaN restants après imputation :")
print(df_imputed.isnull().sum())



# ===============================
# 3) Statistiques
# ===============================
print("\n===== STAT NUMÉRIQUES =====")
print(df_imputed.describe())

print("\n===== STAT CATÉGORIELLES =====")
print(df_imputed.describe(include=["object", "string"]))

# ===============================
# VISUELS - DATASET 2 (df_imputed)
# ===============================

print("\n===== VISUELS DATASET 2 =====")

# -------------------------------
# A) Distributions numériques (histogrammes)
# -------------------------------
num_cols2 = ["Age", "Hours_Per_Week", "Work_Life_Balance_Score", "Social_Isolation_Score"]

df_imputed[num_cols2].hist(figsize=(12, 8), bins=20)
plt.suptitle("Dataset 2 - Distributions des variables numériques", y=1.02)
plt.tight_layout()
plt.show()

# -------------------------------
# B) Whisker Boxplots (outliers) pour variables numériques
# -------------------------------
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_imputed[num_cols2])
plt.title("Dataset 2 - Whisker Boxplot (détection outliers) - Numériques")
plt.xticks(rotation=25)
plt.tight_layout()
plt.show()

# -------------------------------
# C) Boxplots utiles : numérique VS salaire (catégoriel)
# (Pour comprendre ce qui influence la tranche de salaire)
# -------------------------------
plt.figure(figsize=(12, 6))
sns.boxplot(x="Salary_Range", y="Age", data=df_imputed)
plt.title("Age vs Salary_Range")
plt.xticks(rotation=25)
plt.tight_layout()
plt.show()

plt.figure(figsize=(12, 6))
sns.boxplot(x="Salary_Range", y="Hours_Per_Week", data=df_imputed)
plt.title("Hours_Per_Week vs Salary_Range")
plt.xticks(rotation=25)
plt.tight_layout()
plt.show()

plt.figure(figsize=(12, 6))
sns.boxplot(x="Salary_Range", y="Work_Life_Balance_Score", data=df_imputed)
plt.title("Work_Life_Balance_Score vs Salary_Range")
plt.xticks(rotation=25)
plt.tight_layout()
plt.show()

# -------------------------------
# D) Variables catégorielles (countplots)
# -------------------------------
cat_cols2 = ["Gender", "Region", "Industry", "Work_Arrangement", "Burnout_Level", "Salary_Range"]

plt.figure(figsize=(16, 10))
for i, col in enumerate(cat_cols2):
    plt.subplot(3, 2, i + 1)
    sns.countplot(x=col, data=df_imputed, order=df_imputed[col].value_counts().index)
    plt.title(f"Distribution: {col}")
    plt.xticks(rotation=35)
plt.tight_layout()
plt.show()

# -------------------------------
# E) Diagramme "répartition salaire par catégorie"
# Exemple : Salary_Range par Work_Arrangement
# -------------------------------
plt.figure(figsize=(12, 6))
sns.countplot(x="Work_Arrangement", hue="Salary_Range", data=df_imputed,
              order=df_imputed["Work_Arrangement"].value_counts().index)
plt.title("Salary_Range par Work_Arrangement")
plt.xticks(rotation=25)
plt.tight_layout()
plt.show()

# -------------------------------
# F) Heatmap corrélation (numérique)
# -------------------------------
corr2 = df_imputed[num_cols2].corr()
plt.figure(figsize=(8, 6))
sns.heatmap(corr2, annot=True, cmap="coolwarm", fmt=".2f")
plt.title("Dataset 2 - Corrélations (numériques)")
plt.tight_layout()
plt.show()

# ===============================
# Corrélation avec variables catégorielles (corrigée)
# ===============================

print("\n===== CORRÉLATION AVEC VARIABLES CATÉGORIELLES (ENCODÉES) =====")

df_encoded2 = df_imputed.copy()

# 1) Transformer la date en numérique
if "Survey_Date" in df_encoded2.columns:
    df_encoded2["Survey_Date"] = pd.to_datetime(df_encoded2["Survey_Date"])
    df_encoded2["Survey_Date"] = df_encoded2["Survey_Date"].astype("int64") // 10**9
    print("Survey_Date convertie en timestamp numérique")

# 2) Encoder les colonnes catégorielles
label_enc = LabelEncoder()

for col in df_encoded2.columns:
    if df_encoded2[col].dtype == "object":
        df_encoded2[col] = label_enc.fit_transform(df_encoded2[col].astype(str))

# 3) Garder seulement les colonnes numériques
df_encoded2 = df_encoded2.select_dtypes(include=["number"])

# 4) Corrélation
corr_cat = df_encoded2.corr()

plt.figure(figsize=(14, 12))
sns.heatmap(corr_cat, annot=True, fmt=".2f", cmap="coolwarm")

plt.title("Dataset 2 - Corrélation avec encodage catégoriel")
plt.tight_layout()
plt.show()

print("\n✅ Corrélation catégorielle calculée sans erreur")



print("\n✅ Visuels Dataset 2 terminés !")
# ===============================
# 1) Charger dataset
# ===============================
BASE_DIR3 = os.path.dirname(__file__)
file_path3 = os.path.join(BASE_DIR3, "..", "..", "data", "Stress.csv")

df3 = pd.read_csv(file_path3)

print("\n===== APERÇU DES DONNÉES =====")
print(df3.head())

print("\n===== INFORMATIONS DATASET =====")
print(df3.info())

print("\n===== TAILLE DATASET =====")
print(df3.shape)

print("\n===== NOMS DES COLONNES =====")
print(df3.columns)

# ===============================
# 2) Valeurs manquantes
# ===============================
print("\n===== VALEURS MANQUANTES =====")
missing = df3.isnull().sum()
print(missing)

print("\n% valeurs manquantes :")
print((missing / len(df3)) * 100)

# ===============================
# 3) Statistiques
# ===============================
print("\n===== STATISTIQUES NUMÉRIQUES =====")
print(df3.describe())

print("\n===== STATISTIQUES CATÉGORIELLES =====")
print(df3.describe(include=["object", "string"]))

# ===============================
# 4) Distributions numériques
# ===============================
print("\n===== DISTRIBUTIONS NUMÉRIQUES =====")

numeric_df = df3.select_dtypes(include=["number"])

numeric_df.hist(figsize=(12, 10))
plt.suptitle("Distribution des variables numériques", y=1.02)
plt.tight_layout()
plt.show()

# ===============================
# 5) Boxplots (détection visuelle outliers)
# ===============================
print("\n===== BOXPLOTS =====")

plt.figure(figsize=(12, 8))
sns.boxplot(data=numeric_df)
plt.title("Boxplot des variables numériques")
plt.xticks(rotation=45)
plt.show()

# ===============================
# 6) Corrélation numérique
# ===============================
print("\n===== CORRÉLATION NUMÉRIQUE =====")

corr_num = numeric_df.corr()

plt.figure(figsize=(10, 8))
sns.heatmap(corr_num, annot=True, fmt=".2f", cmap="coolwarm")
plt.title("Corrélation des variables numériques")
plt.tight_layout()
plt.show()

# ===============================
# ===============================
# Corrélation avec variables catégorielles (corrigée)
# ===============================

print("\n===== CORRÉLATION AVEC VARIABLES CATÉGORIELLES (ENCODÉES) =====")

df_encoded3 = df3.copy()

# 1) Transformer la date en numérique
if "Survey_Date" in df_encoded3.columns:
    df_encoded3["Survey_Date"] = pd.to_datetime(df_encoded3["Survey_Date"])
    df_encoded3["Survey_Date"] = df_encoded3["Survey_Date"].astype("int64") // 10**9
    print("Survey_Date convertie en timestamp numérique")

# 2) Encoder les colonnes catégorielles
label_enc = LabelEncoder()

for col in df_encoded3.columns:
    if df_encoded3[col].dtype == "object":
        df_encoded3[col] = label_enc.fit_transform(df_encoded3[col].astype(str))

# 3) Garder seulement les colonnes numériques
df_encoded3 = df_encoded3.select_dtypes(include=["number"])

# 4) Corrélation
corr_cat = df_encoded3.corr()

plt.figure(figsize=(14, 12))
sns.heatmap(corr_cat, annot=True, fmt=".2f", cmap="coolwarm")
plt.title("Dataset 3 - Corrélation avec encodage catégoriel")
plt.tight_layout()
plt.show()

print("\n✅ Corrélation catégorielle calculée sans erreur")


print("\n✅ Analyse Stress.csv terminée !")
