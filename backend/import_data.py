import pandas as pd
from pathlib import Path
import sys

# Allow running as a script (`python backend/import_data.py`) by ensuring the
# repository root is on sys.path, so `backend.*` imports resolve.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.database import SessionLocal
from backend.app.models import Recipe

db = SessionLocal()

_CSV_PATH = Path(__file__).resolve().parent / "data" / "recipes.csv"
df = pd.read_csv(_CSV_PATH)

for _, row in df.iterrows():

    recipe = Recipe(

        name = row["name"],
        ingredients = row["ingredients"],
        cuisine = row["cuisine"],
        instructions = row["instructions"]
    )

    db.add(recipe)

db.commit()
db.close()
print("Recipes imported successfully")