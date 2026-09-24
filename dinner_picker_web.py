import streamlit as st
import pandas as pd
import random
from collections import Counter
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import yaml
import streamlit_authenticator as stauth


# ------------------------------------------------------------
# Auth config (single user: Jo)
# ------------------------------------------------------------
def get_auth_config():
    # Hash the password once at startup
    plain_password = "Gr33nL00p0r@ng3"
    hashed_password = stauth.Hasher([plain_password]).generate()[0]

    config = {
        "credentials": {
            "usernames": {
                "Dinners4J0": {
                    "email": "jo@example.com",
                    "name": "Jo",
                    "password": hashed_password,
                }
            }
        },
        "cookie": {
            "expiry_days": 30,
            "key": "some_random_signature_key",
            "name": "dinner_picker_cookie",
        },
        "preauthorized": {
            "emails": []
        },
    }
    return config


# ------------------------------------------------------------
# Load spreadsheet safely (works on Streamlit Cloud)
# ------------------------------------------------------------
def get_excel_path():
    return os.path.join(os.path.dirname(__file__), "dinner options.xlsx")


def load_data():
    excel_path = get_excel_path()
    meals_df = pd.read_excel(excel_path, sheet_name="Recipes")
    ingredients_df = pd.read_excel(excel_path, sheet_name="Ingredients")
    return meals_df, ingredients_df


# ------------------------------------------------------------
# Choose meals with weighted randomness + Daniel rule
# ------------------------------------------------------------
def choose_meals(df, n):
    chosen = []
    meat_count = {}
    carb_count = {}

    # Weighted list
    weighted_options = []
    for _, row in df.iterrows():
        weight = int(row["Rating"])
        weighted_options.extend([row.to_dict()] * weight)

    random.shuffle(weighted_options)

    # STEP 1 — Ensure at least one Daniel meal
    daniel_meals = [
        m for m in weighted_options
        if str(m["Daniel Meal"]).strip().lower() == "yes"
    ]

    if daniel_meals:
        first_daniel = daniel_meals[0]
        chosen.append(first_daniel)
        meat_count[first_daniel["Meat"]] = 1
        carb_count[first_daniel["Carb"]] = 1

    # STEP 2 — Fill remaining slots
    for meal in weighted_options:
        if meal in chosen:
            continue

        meat = meal["Meat"]
        carb = meal["Carb"]

        if meat_count.get(meat, 0) >= 2:
            continue
        if carb_count.get(carb, 0) >= 2:
            continue

        chosen.append(meal)
        meat_count[meat] = meat_count.get(meat, 0) + 1
        carb_count[carb] = carb_count.get(carb, 0) + 1

        if len(chosen) == n:
            break

    return chosen


# ------------------------------------------------------------
# Ingredients + shopping list
# ------------------------------------------------------------
def get_ingredients_for_meal(meal_name, ingredients_df):
    rows = ingredients_df[ingredients_df.iloc[:, 0] == meal_name]
    return [row.iloc[1] for _, row in rows.iterrows()]


def build_shopping_list(meals, ingredients_df):
    counter = Counter()
    for meal in meals:
        ingredients = get_ingredients_for_meal(meal["Meal Name"], ingredients_df)
        for ingredient in ingredients:
            counter[ingredient] += 1
    return counter


# ------------------------------------------------------------
# PDF generation
# ------------------------------------------------------------
def generate_pdf(meals, ingredients_df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Weekly Dinner Plan")
    y -= 30

    c.setFont("Helvetica", 12)

    for m in meals:
        if y < 80:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, "Weekly Dinner Plan (cont.)")
            y -= 30
            c.setFont("Helvetica", 12)

        c.drawString(40, y, f"Meal: {m['Meal Name']}")
        y -= 16
        c.drawString(40, y, f"Link: {m['Link']}")
        y -= 16
        c.drawString(40, y, f"Method: {m['Method']}")
        y -= 16
        c.drawString(40, y, f"Notes: {m['Notes']}")
        y -= 16

        ingredients = get_ingredients_for_meal(m["Meal Name"], ingredients_df)
        c.drawString(40, y, "Ingredients:")
        y -= 16
        for ing in ingredients:
            c.drawString(60, y, f"- {ing}")
            y -= 14

        y -= 10

    # Shopping list
    shopping = build_shopping_list(meals, ingredients_df)

    if y < 120:
        c.showPage()
        y = height - 40

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Shopping List")
    y -= 30
    c.setFont("Helvetica", 12)

    for item, count in shopping.items():
        if y < 60:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, "Shopping List (cont.)")
            y -= 30
            c.setFont("Helvetica", 12)
        c.drawString(40, y, f"- {item} x{count}")
        y -= 16

    c.save()
    buffer.seek(0)
    return buffer


# ------------------------------------------------------------
# Spreadsheet upload (update dinners.xlsx)
# ------------------------------------------------------------
def handle_upload():
    st.subheader("Update spreadsheet")
    uploaded_file = st.file_uploader("Upload a new dinners.xlsx", type=["xlsx"])
    if uploaded_file is not None:
        excel_path = get_excel_path()
        with open(excel_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Spreadsheet updated. Reload the page to use the new data.")


# ------------------------------------------------------------
# Main app with login
# ------------------------------------------------------------
def main():
    st.set_page_config(page_title="Weekly Dinner Picker", page_icon="🍽️")

    config = get_auth_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        config["preauthorized"],
    )

    name, authentication_status, username = authenticator.login("Login", "main")

    if authentication_status is False:
        st.error("Username or password is incorrect.")
        return
    elif authentication_status is None:
        st.warning("Please enter your username and password.")
        return

    # Authenticated
    authenticator.logout("Logout", "sidebar")
    st.sidebar.write(f"Logged in as {name}")

    st.title("Weekly Dinner Picker 🍽️")
    st.write("Generate your weekly meal plan, download it as a PDF, and keep your spreadsheet up to date.")

    handle_upload()

    meals_df, ingredients_df = load_data()

    n = st.slider("Number of meals this week:", 1, 10, 5)

    if st.button("Generate Meal Plan"):
        meals = choose_meals(meals_df, n)

        st.subheader("Your Dinner Plan")
        for m in meals:
            st.markdown(f"### {m['Meal Name']}")
            st.markdown(f"**Link:** {m['Link']}")
            st.markdown(f"**Method:** {m['Method']}")
            st.markdown(f"**Notes:** {m['Notes']}")

            ingredients = get_ingredients_for_meal(m["Meal Name"], ingredients_df)
            st.markdown("**Ingredients:**")
            st.write(ingredients)

        shopping = build_shopping_list(meals, ingredients_df)
        st.subheader("Shopping List")
        st.write(shopping)

        pdf_buffer = generate_pdf(meals, ingredients_df)
        st.download_button(
            label="Download PDF Meal Plan",
            data=pdf_buffer,
            file_name="weekly_dinner_plan.pdf",
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()

