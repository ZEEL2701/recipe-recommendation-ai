import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from groq import Groq

from .database import engine
from .models import Base
from .recommender import recommend_recipes
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


def generate_ai_recipe(recipe_name: str, ingredients: str) -> str:
    """
    Writes a full recipe for the dish the recommender already matched.
    The model should treat this as the same recommendation the user saw in the app.
    """
    groq = _groq_client()
    prompt = f"""
    You are the writing assistant for a recipe recommender app.

    The recommender already matched the user's ingredients to this dish from its catalog:
    **{recipe_name}**

    Base ingredient list from that match (use these; you may add small pantry staples if needed):
    {ingredients}

    Write one complete recipe for the user: short intro, ingredient list with amounts where reasonable,
    clear step-by-step instructions, and serving tips. Do not claim a different dish name —
    stay faithful to "{recipe_name}".
    """

    response = groq.chat.completions.create(
        model=_DEFAULT_GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt.strip(),
            }
        ],
        temperature=0.5,
    )

    content = response.choices[0].message.content
    return (content or "").strip()


app = FastAPI(
    title="Recipe Recommender API",
)

Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "Recipe Recommendation API Running",
    }


@app.post("/recommend")
def recommend(data: RecommendationRequest):
    recommendations = recommend_recipes(
        data.ingredients,
    )

    return {
        "recommendations": recommendations,
    }


@app.post("/generate-recipe")
def generate_recipe(data: RecommendationRequest):
    """
    Same flow as /recommend: we pick the best catalog match from the user's ingredients,
    then generate a full write-up. For the UI this still reads as "recommended for you."
    """
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured.",
        )

    recommendations = recommend_recipes(
        data.ingredients,
        top_n=1,
    )

    if not recommendations:
        raise HTTPException(
            status_code=404,
            detail="No matching recipe found for those ingredients.",
        )

    best_recipe = recommendations[0]

    full_recipe_text = generate_ai_recipe(
        best_recipe["name"],
        best_recipe["ingredients"],
    )

    return {
        # Backward-compatible keys
        "recommended_recipe": best_recipe["name"],
        "generated_recipe": full_recipe_text,
        # Clear story for the frontend: catalog match + generated detail
        "recommended_title": best_recipe["name"],
        "catalog_cuisine": best_recipe["cuisine"],
        "catalog_ingredients": best_recipe["ingredients"],
        "catalog_instructions": best_recipe["instructions"],
        "full_recipe": full_recipe_text,
        "tagline": (
            "Personalized recipe for your best match — "
            "the dish name comes from the recommender; steps are generated for you."
        ),
    }
