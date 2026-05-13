import os

import requests
import streamlit as st

# Full URL to POST /recommend (no trailing slash issues).
# Override locally: set RECOMMEND_API_URL or add to .streamlit/secrets.toml on Streamlit Cloud:
# RECOMMEND_API_URL = "https://your-service.onrender.com/recommend"
_DEFAULT_API = "https://recipe-recommendation-ai.onrender.com/recommend"


def _recommend_url() -> str:
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
    """Strip /recommend so we can call /generate-recipe on the same host."""
    rec = _recommend_url()
    if rec.endswith("/recommend"):
        return rec[: -len("/recommend")].rstrip("/")
    return rec.rstrip("/")


def _generate_recipe_url() -> str:
    return f"{_api_base_url()}/generate-recipe"


st.set_page_config(
    page_title="Recipe Recommendation AI",
    page_icon="🍲",
    layout="wide"
)


# CUSTOM CSS
st.markdown("""
<style>

.main {
    padding-top: 2rem;
}

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

.recipe-text {
    color: #dcdcdc;
    font-size: 16px;
}

.best-match {
    border: 2px solid #ffb703;
}

</style>
""", unsafe_allow_html=True)


st.title("🍲 Recipe Recommendation AI")

st.write(
    "Discover recipes based on ingredients you already have."
)


ingredients = st.text_input(
    "Enter Ingredients",
    placeholder="tomato onion cheese"
)


if st.button("Recommend Recipes"):

    if ingredients.strip() == "":
        st.warning("Please enter ingredients")

    else:
        api_url = _recommend_url()

        try:
            # Render free tier can cold-start ~30–60s; avoid silent hangs.
            response = requests.post(
                api_url,
                json={"ingredients": ingredients},
                timeout=120,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.Timeout:
            st.error(
                "The API took too long to respond. On Render’s free tier the first "
                "request after sleep can take a minute—try again once."
            )
            st.stop()
        except requests.exceptions.RequestException as e:
            st.error(f"Could not reach the API at `{api_url}`. Check the URL and your network.\n\n{e}")
            st.stop()

        if response.status_code != 200:
            st.error(
                f"API returned **{response.status_code}**. "
                f"Body (first 500 chars):\n\n```\n{response.text[:500]}\n```"
            )
            st.stop()

        try:
            data = response.json()
        except ValueError:
            st.error("API did not return JSON. Is the URL correct?")
            st.stop()

        recommendations = data.get("recommendations")
        if recommendations is None:
            st.error("Unexpected response: missing `recommendations` key.")
            st.stop()

        if recommendations:

            st.subheader("⭐ Best Match")

            best_recipe = recommendations[0]

            st.markdown(
                f"""
                <div class="recipe-card best-match">

                <div class="recipe-title">
                {best_recipe['name']}
                </div>

                <br>

                <div class="recipe-text">
                🍽 <b>Cuisine:</b> {best_recipe['cuisine']}
                </div>

                <br>

                <div class="recipe-text">
                🥘 <b>Ingredients:</b><br>
                {best_recipe['ingredients']}
                </div>

                <br>

                <div class="recipe-text">
                📖 <b>Instructions:</b><br>
                {best_recipe['instructions']}
                </div>

                </div>
                """,
                unsafe_allow_html=True
            )

            st.subheader("✨ AI recipe (optional)")
            st.caption(
                "Uses your backend `/generate-recipe` (Groq). "
                "Requires `GROQ_API_KEY` on Render."
            )
            if st.button("Expand best match with AI", key="gen_ai"):
                gen_url = _generate_recipe_url()
                with st.spinner("Generating detailed recipe…"):
                    try:
                        gen_resp = requests.post(
                            gen_url,
                            json={"ingredients": ingredients},
                            timeout=120,
                            headers={"Content-Type": "application/json"},
                        )
                    except requests.exceptions.RequestException as e:
                        st.error(f"Could not call `{gen_url}`: {e}")
                    else:
                        if gen_resp.status_code == 503:
                            st.warning(
                                "API key missing: set **GROQ_API_KEY** in Render environment variables."
                            )
                        elif gen_resp.status_code == 404:
                            st.info(gen_resp.json().get("detail", "No match for AI expansion."))
                        elif gen_resp.status_code != 200:
                            st.error(
                                f"**{gen_resp.status_code}** — {gen_resp.text[:800]}"
                            )
                        else:
                            try:
                                payload = gen_resp.json()
                            except ValueError:
                                st.error("Response was not JSON.")
                            else:
                                st.markdown(
                                    f"**{payload.get('recommended_recipe', 'Recipe')}**\n\n"
                                    f"{payload.get('generated_recipe', '')}"
                                )

            if len(recommendations) > 1:
                st.subheader("More Recipes")

                cols = st.columns(2)

                for idx, recipe in enumerate(recommendations[1:]):

                    with cols[idx % 2]:

                        st.markdown(
                            f"""
                            <div class="recipe-card">

                            <div class="recipe-title">
                            {recipe['name']}
                            </div>

                            <br>

                            <div class="recipe-text">
                            🍽 <b>Cuisine:</b> {recipe['cuisine']}
                            </div>

                            <br>

                            <div class="recipe-text">
                            🥘 <b>Ingredients:</b><br>
                            {recipe['ingredients']}
                            </div>

                            <br>

                            <div class="recipe-text">
                            📖 <b>Instructions:</b><br>
                            {recipe['instructions']}
                            </div>

                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        else:
            st.info(
                "No recipes matched those ingredients (or the score was below the API threshold). "
                "Try different or more ingredients."
            )