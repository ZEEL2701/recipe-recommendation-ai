from fastapi import FastAPI

from .database import engine
from .models import Base
from .recommender import recommend_recipes
from .schemas import RecommendationRequest


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