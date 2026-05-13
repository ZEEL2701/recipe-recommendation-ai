import pandas as pd
from pathlib import Path
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import hstack

_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "recipes.csv"
if not _CSV_PATH.exists():
    raise FileNotFoundError(
        f"recipes.csv not found at {_CSV_PATH}. "
        "Ensure `backend/data/recipes.csv` is committed and deployed (Render Root Directory = backend)."
    )
df = pd.read_csv(_CSV_PATH)

# Normalize column names to safely index them
df.columns = [str(c).strip().lower() for c in df.columns]

df["ingredients"] = df["ingredients"].fillna("")

# Irregular / tricky plurals (blind "strip trailing s" turns "tomatoes" → "tomatoe").
_PLURAL_TO_SINGULAR = {
    "tomatoes": "tomato",
    "potatoes": "potato",
    "onions": "onion",
    "carrots": "carrot",
    "beans": "bean",
    "peas": "pea",
    "mushrooms": "mushroom",
    "noodles": "noodle",
    "apples": "apple",
    "bananas": "banana",
    "mangoes": "mango",
    "grapes": "grape",
    "eggs": "egg",
    "spices": "spice",
    "herbs": "herb",
    "lentils": "lentil",
    "chickpeas": "chickpea",
}

# Fixes after naive singularization
_TOKEN_FIXES = {
    "tomatoe": "tomato",
    "potatoe": "potato",
}


def _singularize_token(t: str) -> str:
    if t in _PLURAL_TO_SINGULAR:
        return _PLURAL_TO_SINGULAR[t]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        stem = t[:-1]
        return _TOKEN_FIXES.get(stem, stem)
    return t


def _normalize_ingredients(text: str) -> str:
    """
    Normalize ingredient text so small variants (e.g., potato vs potatoes, commas)
    still match reasonably with TF-IDF word tokens.
    """
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s,]", " ", text)
    text = text.replace(",", " ")
    tokens = [t for t in text.split() if t]

    normalized: list[str] = []
    for t in tokens:
        normalized.append(_singularize_token(t))

    return " ".join(normalized)


df["_ingredients_norm"] = df["ingredients"].map(_normalize_ingredients)
df["_ingredients_tokens"] = df["_ingredients_norm"].str.split().map(lambda xs: [x for x in xs if x])
df["_ingredients_token_count"] = df["_ingredients_tokens"].map(len)

# For ranking: query words appearing in the recipe *title* (e.g. "tomato" → "Tomato Pasta").
df["_name_tokens"] = (
    df["name"].astype(str).map(_normalize_ingredients).str.split().map(lambda xs: set(x for x in xs if x))
)

# Unmatched tokens like egg/chicken when the user did not ask for them skew results; penalize lightly.
_STRONG_EXTRAS = frozenset(
    {
        "egg",
        "chicken",
        "fish",
        "paneer",
        "beef",
        "pork",
        "mutton",
        "lamb",
        "turkey",
        "prawn",
        "shrimp",
        "mushroom",
        "chickpea",
        "chickpeas",
    }
)

_word_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
_char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))

_word_matrix = _word_vectorizer.fit_transform(df["_ingredients_norm"])
_char_matrix = _char_vectorizer.fit_transform(df["_ingredients_norm"])
tfidf_matrix = hstack([_word_matrix, _char_matrix])

def recommend_recipes(user_input, top_n = 3, min_score: float = 0.08):
    user_input_norm = _normalize_ingredients(user_input)
    query_tokens = [t for t in user_input_norm.split() if t]
    query_set = set(query_tokens)
    query_len = max(len(query_set), 1)

    user_word = _word_vectorizer.transform([user_input_norm])
    user_char = _char_vectorizer.transform([user_input_norm])
    user_vector = hstack([user_word, user_char])

    similarity_scores = cosine_similarity(
        user_vector,
        tfidf_matrix
    )

    scores = similarity_scores.flatten()

    # If keyword does not match, avoid returning arbitrary recipes.
    if scores.max(initial=0) < float(min_score):
        return []

    # Pull a larger candidate set using TF-IDF, then rerank using token-overlap metrics.
    # This makes results more intuitive for both single-ingredient and multi-ingredient
    # queries (prefer matching more of what the user asked for, and fewer unrelated extras).
    ranked = scores.argsort()[::-1]
    candidate_limit = min(50, len(ranked))
    candidates = [i for i in ranked[:candidate_limit] if scores[i] >= float(min_score)]

    def rerank_key(i: int):
        tokens = df.at[i, "_ingredients_tokens"]
        token_set = set(tokens)
        overlap = len(token_set & query_set)
        recall = overlap / query_len  # how much of the query is covered
        precision = overlap / max(len(token_set), 1)  # how focused the recipe is
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        extras = max(len(token_set) - overlap, 0)
        extra_tokens = token_set - query_set
        strong_extra_penalty = sum(3 if t in _STRONG_EXTRAS else 1 for t in extra_tokens)
        name_hits = len(query_set & df.at[i, "_name_tokens"])
        # Slight boost when the dish name echoes what the user typed (e.g. "tomato" → Tomato Pasta).
        effective_match = float(f1) + 0.15 * float(name_hits)

        # Sort descending: effective score, title hits, fewer "unrelated" extras, then cosine.
        return (
            effective_match,
            float(name_hits),
            -float(strong_extra_penalty),
            float(recall),
            float(precision),
            float(scores[i]),
            -extras,
            -int(df.at[i, "_ingredients_token_count"]),
        )

    candidates.sort(key=rerank_key, reverse=True)
    top_indices = candidates[:top_n]

    recommendations = []

    for idx in top_indices:
        recipe = {
            "name": df.loc[idx]["name"],
            "ingredients": df.loc[idx]["ingredients"],
            "cuisine": df.loc[idx]["cuisine"],
            "instructions": df.loc[idx]["instructions"],
            "similarity_score": float(scores[idx]),
        }
        recommendations.append(recipe)

    return recommendations
