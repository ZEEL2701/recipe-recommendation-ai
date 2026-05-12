import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000/recommend"


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

        response = requests.post(
            API_URL,
            json={
                "ingredients": ingredients
            }
        )

        data = response.json()

        recommendations = data["recommendations"]

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