import pandas as pd
from pathlib import Path
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import hstack

_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "recipes.csv"
df = pd.read_csv(_CSV_PATH)

# Normalize column names to safely index them
df.columns = [str(c).strip().lower() for c in df.columns]

df["ingredients"] = df["ingredients"].fillna("")

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
        if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us")):
            normalized.append(t[:-1])
        else:
            normalized.append(t)

    return " ".join(normalized)


df["_ingredients_norm"] = df["ingredients"].map(_normalize_ingredients)
df["_ingredients_tokens"] = df["_ingredients_norm"].str.split().map(lambda xs: [x for x in xs if x])
df["_ingredients_token_count"] = df["_ingredients_tokens"].map(len)

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

        # Sort descending by: F1, recall, precision, cosine; prefer fewer extras and fewer ingredients.
        return (
            float(f1),
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
