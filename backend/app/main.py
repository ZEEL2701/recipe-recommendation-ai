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

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_ai_recipe(recipe_name: str, ingredients: str) -> str:
    prompt = f"""
    Generate a detailed recipe.

    Recipe Name:
    {recipe_name}

    Ingredients:
    {ingredients}

    Include:
    - recipe introduction
    - step-by-step instructions
    - serving suggestions

    keep it professional and engaging.
    """

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content


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

    generated_recipe = generate_ai_recipe(
        best_recipe["name"],
        best_recipe["ingredients"],
    )

    return {
        "recommended_recipe": best_recipe["name"],
        "generated_recipe": generated_recipe,
    }
