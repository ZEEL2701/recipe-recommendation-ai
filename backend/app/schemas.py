from typing import Optional

from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    ingredients: str
    allergies: Optional[str] = None
    cuisine: Optional[str] = None
    # Used by /generate-recipe so the AI expands the same dish that /recommend returned.
    recipe_name: Optional[str] = None
    recipe_ingredients: Optional[str] = None


class RecipeResponse(BaseModel):
    name: str
    ingredients: str
    cuisine: str
    instructions: str
    similarity_score: float
