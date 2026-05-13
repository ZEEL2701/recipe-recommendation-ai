from fastapi import FastAPI

from .database import engine
from .models import Base
from .recommender import recommend_recipes
from .schemas import RecommendationRequest
from groq import Groq
from dotenv import load_dotenv

load_dotenv("backend/.env")

client = Groq(
    api_key = os.getenv("GROQ_API_KEY")
)

def generate_ai_recipe(recipe_name, ingredients):

    prompt = f"""
    Generate a detailed recipe.

    Recipe Name:
    {recipe_name}

    Ingredients:
    {ingredients}

    Include:
    -recipe introduction
    -step-by-step instructions
    -serving suggestions

    keep it professional and engaging.
    """

response = client.chat.completions.create(
    model = "openai/gpt-oss-120b",

    messages = [
        {
            "role" : "user",
            "content" : prompt
        }
    ],
     temperature = 0.5
)

return response.choices[0].message.content


app = FastAPI(
    title="Recipe Recommender API"
)

Base.metadata.create_all(bind=engine)


@app.get("/")
def home():

    return {
        "message": "Recipe Recommendation API Running"
    }


@app.post("/recommend")
def recommend(data: RecommendationRequest):

    recommendations = recommend_recipes(
        data.ingredients
    )

    return {
        "recommendations": recommendations
    }

@app.post("/generate-recipe")
def generate_recipe(data: RecommendationRequest):

    recommendations = recommend_recipes(
        data.ingredients,
        top_n = 1
    )

    best_recipes = recommendations[0]

    generated_recipe = generate_ai_recipe(
        best_recipe["name"],
        best_recipe["ingredients"]
    )

    return{
        "recommended_recipe": best_recipe["name"],
        "generated_recipe": generated_recipe
    }