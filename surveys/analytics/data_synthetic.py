import pandas as pd
import os
from sdv.single_table import CTGANSynthesizer
from sdv.metadata import SingleTableMetadata

# chemin vers ton fichier
BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "..", "..", "data", "Questionnaire.csv")

# charger données
data = pd.read_csv(file_path)
print("Chemin :", file_path)
print("Shape :", data.shape)
print(data.head())
# créer metadata automatiquement
metadata = SingleTableMetadata()
metadata.detect_from_dataframe(data)

# créer modèle
model = CTGANSynthesizer(metadata)

# entrainer
model.fit(data)

# générer synthetic data
synthetic_data = model.sample(num_rows=10000)

# sauvegarder
output_path = os.path.join(BASE_DIR, "synthetic_data.csv")
synthetic_data.to_csv(output_path, index=False)

print("Synthetic data générée avec succès")
