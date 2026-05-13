import os

import requests
import streamlit as st

# Default backend when nothing else is configured.
_DEFAULT_API = "https://recipe-recommendation-ai.onrender.com/recommend"
#
# API URL resolution (works on self-hosted Streamlit, Docker, VPS, etc.):
#   Set environment variable: RECOMMEND_API_URL=https://your-api.onrender.com/recommend
#   Your process manager or host panel must inject env vars for the Streamlit process.
# Optional: on Streamlit Community Cloud only, you can add the same key to .streamlit/secrets.toml
#   RECOMMEND_API_URL = "https://..."


def _recommend_url() -> str:
    # Prefer OS env — usual for non-Cloud deployments.
    env = os.getenv("RECOMMEND_API_URL", "").strip()
    if env:
        return env.rstrip("/")
    try:
        if "RECOMMEND_API_URL" in st.secrets:
            return str(st.secrets["RECOMMEND_API_URL"]).strip().rstrip("/")
    except (FileNotFoundError, KeyError, TypeError):
        pass
    return _DEFAULT_API.rstrip("/")


def _api_base_url() -> str:
    rec = _recommend_url()
    if rec.endswith("/recommend"):
        return rec[: -len("/recommend")].rstrip("/")
    return rec.rstrip("/")


def _generate_recipe_url() -> str:
    return f"{_api_base_url()}/generate-recipe"


def _init_session():
    if "rec_query" not in st.session_state:
        st.session_state.rec_query = ""
    if "rec_list" not in st.session_state:
        st.session_state.rec_list = None
    if "rec_ai" not in st.session_state:
        st.session_state.rec_ai = None
    if "rec_ai_error" not in st.session_state:
        st.session_state.rec_ai_error = None


_init_session()

st.set_page_config(
    page_title="Recipe Recommendation AI",
    page_icon="🍲",
    layout="wide",
)


st.markdown(
    """
<style>
.main { padding-top: 2rem; }
.recipe-card {
    background-color: #1e1e1e;
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 20px;
}
.recipe-title {
    font-size: 28px;
    font-weight: bold;
    color: white;
}
.recipe-text { color: #dcdcdc; font-size: 16px; }
.best-match { border: 2px solid #ffb703; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🍲 Recipe Recommendation AI")

st.write(
    "Enter what you have — we **recommend** a dish from our catalog, then you can open a **full recipe** "
    "written for that same recommendation."
)

ingredients = st.text_input(
    "Enter Ingredients",
    placeholder="tomato onion cheese",
    key="ingredient_input",
)


def fetch_recommendations():
    q = (st.session_state.get("ingredient_input") or "").strip()
    if not q:
        st.warning("Please enter ingredients")
        return

    api_url = _recommend_url()
    try:
        response = requests.post(
            api_url,
            json={"ingredients": q},
            timeout=120,
            headers={"Content-Type": "application/json"},
        )
    except requests.exceptions.Timeout:
        st.error(
            "The API took too long to respond. On Render’s free tier, try again after a cold start."
        )
        return
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach `{api_url}`.\n\n{e}")
        return

    if response.status_code != 200:
        st.error(
            f"API returned **{response.status_code}**.\n\n```\n{response.text[:500]}\n```"
        )
        return

    try:
        data = response.json()
    except ValueError:
        st.error("API did not return JSON.")
        return

    recs = data.get("recommendations")
    if recs is None:
        st.error("Missing `recommendations` in response.")
        return

    st.session_state.rec_query = q
    st.session_state.rec_list = recs
    st.session_state.rec_ai = None
    st.session_state.rec_ai_error = None


if st.button("Recommend Recipes"):
    fetch_recommendations()


def fetch_ai_recipe():
    q = st.session_state.rec_query
    if not q:
        st.warning("Run **Recommend Recipes** first.")
        return

    gen_url = _generate_recipe_url()
    try:
        gen_resp = requests.post(
            gen_url,
            json={"ingredients": q},
            timeout=120,
            headers={"Content-Type": "application/json"},
        )
    except requests.exceptions.RequestException as e:
        st.session_state.rec_ai_error = str(e)
        st.session_state.rec_ai = None
        return

    if gen_resp.status_code == 503:
        st.session_state.rec_ai_error = (
            "AI is not configured on the server (set **GROQ_API_KEY** on Render)."
        )
        st.session_state.rec_ai = None
        return

    if gen_resp.status_code == 404:
        detail = gen_resp.json().get("detail", "No match.")
        st.session_state.rec_ai_error = detail
        st.session_state.rec_ai = None
        return

    if gen_resp.status_code != 200:
        st.session_state.rec_ai_error = f"{gen_resp.status_code}: {gen_resp.text[:600]}"
        st.session_state.rec_ai = None
        return

    try:
        payload = gen_resp.json()
    except ValueError:
        st.session_state.rec_ai_error = "Invalid JSON from generate-recipe."
        st.session_state.rec_ai = None
        return

    st.session_state.rec_ai = payload
    st.session_state.rec_ai_error = None


if st.session_state.rec_list:
    recommendations = st.session_state.rec_list

    st.subheader("⭐ Best match (from recommender)")

    best_recipe = recommendations[0]

    st.markdown(
        f"""
        <div class="recipe-card best-match">
        <div class="recipe-title">{best_recipe['name']}</div>
        <br>
        <div class="recipe-text">🍽 <b>Cuisine:</b> {best_recipe['cuisine']}</div>
        <br>
        <div class="recipe-text">🥘 <b>Ingredients:</b><br>{best_recipe['ingredients']}</div>
        <br>
        <div class="recipe-text">📖 <b>Instructions:</b><br>{best_recipe['instructions']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Full recipe for your recommendation")
    st.caption(
        "Uses the **same** best match the recommender chose. The long version is generated for that dish — "
        "so it still feels like *your* recommendation, not a random AI recipe."
    )

    if st.button("Get full personalized recipe", key="gen_ai"):
        with st.spinner("Writing your recipe…"):
            fetch_ai_recipe()

    if st.session_state.rec_ai_error:
        st.error(st.session_state.rec_ai_error)

    if st.session_state.rec_ai:
        p = st.session_state.rec_ai
        title = p.get("recommended_title") or p.get("recommended_recipe", "Recipe")
        st.success(f"**{title}** — personalized steps below.")
        if p.get("tagline"):
            st.caption(p["tagline"])
        body = p.get("full_recipe") or p.get("generated_recipe", "")
        st.markdown(body)

    if len(recommendations) > 1:
        st.subheader("More recipes")
        cols = st.columns(2)
        for idx, recipe in enumerate(recommendations[1:]):
            with cols[idx % 2]:
                st.markdown(
                    f"""
                    <div class="recipe-card">
                    <div class="recipe-title">{recipe['name']}</div>
                    <br>
                    <div class="recipe-text">🍽 <b>Cuisine:</b> {recipe['cuisine']}</div>
                    <br>
                    <div class="recipe-text">🥘 <b>Ingredients:</b><br>{recipe['ingredients']}</div>
                    <br>
                    <div class="recipe-text">📖 <b>Instructions:</b><br>{recipe['instructions']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
elif st.session_state.rec_query and st.session_state.rec_list == []:
    st.info(
        "No recipes matched (or similarity was below the API threshold). Try other ingredients."
    )
