from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    ingredients: str


class RecipeResponse(BaseModel):
    name: str
    ingredients: str
    cuisine: str
    instructions: str
    similarity_score: float
