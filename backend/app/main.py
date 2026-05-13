import json
import os
from pathlib import Path
import re
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from groq import Groq

from .schemas import RecommendationRequest

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_PATH)

_DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _groq_client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured.",
        )
    return Groq(api_key=key)


def _parse_allergies(allergies: Optional[str]) -> List[str]:
    if not allergies:
        return []
    # Accept common list styles:
    # - "milk, sugar"
    # - "milk\nsugar"
    # - "milk sugar" (space-separated)
    raw = allergies.strip().lower()
    if not raw:
        return []

    parts = re.split(r"[,\n;]+", raw)
    cleaned: List[str] = []
    for p in parts:
        token = p.strip()
        if not token:
            continue
        cleaned.append(token)
        # If user typed a space-separated list inside one part ("milk sugar"),
        # also include each word as an allergy token.
        if " " in token:
            for w in token.split():
                if w and w not in cleaned:
                    cleaned.append(w)

    return cleaned


def _extract_json_object(text: str) -> dict:
    """
    Best-effort JSON extraction. The model is instructed to return JSON only,
    but this keeps the API resilient if it wraps output in markdown fences.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned)
    cleaned = cleaned.replace("```", "").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    return json.loads(cleaned)


def _allergy_in_text(allergy: str, text: str) -> bool:
    term = allergy.lower().strip()
    if not term:
        return False
    # Avoid false positives like "eggplant" for allergy "egg".
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def generate_top_recipes_ai(
    ingredients: str,
    allergies: Optional[str],
    cuisine: Optional[str],
    top_n: int = 3,
) -> List[dict]:
    """
    GenAI-only recommendation: generate top N recipes based on the user's ingredients
    and avoid any listed allergens.
    """
    allergy_list = _parse_allergies(allergies)

    # If the user enters something both as ingredient and allergy, treat it strictly
    # as an allergy: remove it from the inspiration text before sending to the model.
    cleaned_ingredients = ingredients
    for a in allergy_list:
        if not a:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])"
        cleaned_ingredients = re.sub(pattern, " ", cleaned_ingredients, flags=re.IGNORECASE)
    cleaned_ingredients = re.sub(r"\s+", " ", cleaned_ingredients).strip()

    if not cleaned_ingredients:
        raise HTTPException(
            status_code=400,
            detail=(
                "No usable ingredients remain after applying allergies. "
                "Please remove conflicting entries or add alternative ingredients."
            ),
        )

    groq = _groq_client()
    candidate_n = max(6, top_n * 2)

    allergy_text = ", ".join(allergy_list) if allergy_list else "none"
    cuisine_text = (cuisine or "").strip() or "any"

    prompt = f"""
You are a careful recipe generator.

User ingredients (use as inspiration; you may add common pantry staples if needed):
{cleaned_ingredients}

Allergies to avoid (must NOT appear in the recipe ingredients or instructions):
{allergy_text}

Preferred cuisine (strictly prefer this when possible):
{cuisine_text}

Task:
Generate {candidate_n} candidate recipes. Then the API will filter to the top {top_n}
that best satisfy the user's ingredients and avoid allergies.

Rules:
- Output ONLY valid JSON (no markdown, no extra text).
- JSON schema:
{{
  "recommendations": [
    {{
      "name": string,
      "cuisine": string,
      "ingredients": string,      // multiline text with amounts when reasonable
      "instructions": string      // step-by-step text
    }}
  ]
}}
- Each recommendation must be a distinct dish.
- If preferred cuisine is provided (not "any"), keep all recommendations in that cuisine.
- Do not include any allergic ingredient (or close equivalents) anywhere in ingredients/instructions.
"""

    response = groq.chat.completions.create(
        model=_DEFAULT_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt.strip()}],
        temperature=0.7,
    )

    raw = response.choices[0].message.content or ""
    try:
        data = _extract_json_object(raw)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned invalid JSON for recommendations: {str(e)[:200]}",
        )
    candidates = data.get("recommendations") or []

    filtered: List[dict] = []
    for r in candidates:
        name = (r.get("name") or "").strip()
        cuisine = (r.get("cuisine") or "").strip()
        ing = (r.get("ingredients") or "").strip()
        instr = (r.get("instructions") or "").strip()

        combined = f"{name}\n{ing}\n{instr}"
        if any(_allergy_in_text(a, combined) for a in allergy_list):
            continue

        filtered.append(
            {
                "name": name,
                "cuisine": cuisine,
                "ingredients": ing,
                "instructions": instr,
            }
        )

        if len(filtered) >= top_n:
            break

    return filtered


def generate_recipe_detail_ai(
    recipe_name: str,
    recipe_ingredients: str,
    allergies: Optional[str],
    cuisine: Optional[str],
) -> str:
    groq = _groq_client()
    allergy_list = _parse_allergies(allergies)
    allergy_text = ", ".join(allergy_list) if allergy_list else "none"
    cuisine_text = (cuisine or "").strip() or "any"

    prompt = f"""
You are writing the final detailed recipe for a dish selected by the recommender.

Dish name (do not change):
{recipe_name}

Base ingredients for the selected match (use these; you may refine amounts):
{recipe_ingredients}

Allergies to avoid (do not include in ingredients or instructions):
{allergy_text}

Preferred cuisine context:
{cuisine_text}

Output ONLY valid JSON with this schema:
{{
  "full_recipe": string,      // include intro + ingredients + numbered instructions
  "tagline": string
}}
"""

    response = groq.chat.completions.create(
        model=_DEFAULT_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt.strip()}],
        temperature=0.5,
    )

    raw = response.choices[0].message.content or ""
    try:
        data = _extract_json_object(raw)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned invalid JSON for recipe detail: {str(e)[:200]}",
        )

    full_recipe = (data.get("full_recipe") or "").strip()
    if not full_recipe:
        raise HTTPException(status_code=502, detail="AI returned empty recipe text.")

    return full_recipe


app = FastAPI(
    title="Recipe Recommender API",
)


@app.get("/")
def home():
    return {
        "message": "Recipe Recommendation API Running",
    }


@app.post("/recommend")
def recommend(data: RecommendationRequest):
    recommendations = generate_top_recipes_ai(
        ingredients=data.ingredients,
        allergies=data.allergies,
        cuisine=data.cuisine,
        top_n=3,
    )

    if not recommendations:
        raise HTTPException(
            status_code=404,
            detail=(
                "No recipes could be generated that satisfy your ingredients/allergies. "
                "If you listed the same item as both an ingredient and an allergy, "
                "please remove it from one of the fields or choose a substitute."
            ),
        )

    return {"recommendations": recommendations}


@app.post("/generate-recipe")
def generate_recipe(data: RecommendationRequest):
    if not data.recipe_name:
        raise HTTPException(
            status_code=400,
            detail="recipe_name is required for /generate-recipe.",
        )

    full_recipe_text = generate_recipe_detail_ai(
        recipe_name=data.recipe_name,
        recipe_ingredients=data.recipe_ingredients or "",
        allergies=data.allergies,
        cuisine=data.cuisine,
    )

    return {
        "recommended_recipe": data.recipe_name,
        "recommended_title": data.recipe_name,
        "generated_recipe": full_recipe_text,
        "full_recipe": full_recipe_text,
        "tagline": "AI expanded your recommended recipe (with your allergy constraints).",
    }
