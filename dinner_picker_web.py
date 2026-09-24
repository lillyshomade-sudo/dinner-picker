import streamlit as st
import pandas as pd
import random
from collections import Counter
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ------------------------------------------------------------
# Load spreadsheet
# ------------------------------------------------------------
@st.cache_data

def load_data(filename):
    meals_df = pd.read_excel(filename, sheet_name="Recipes")
    ingredients_df = pd.read_excel(filename, sheet_name="Ingredients")
    return meals_df, ingredients_df


# ------------------------------------------------------------
# Weighted random choice with meat/carb limits
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

    # STEP 1 — Try to pick at least one Daniel meal
    daniel_meals = [m for m in weighted_options if str(m["Daniel Meal"]).lower() == "yes"]

    if daniel_meals:
        first_daniel = daniel_meals[0]
        chosen.append(first_daniel)
        meat_count[first_daniel["Meat"]] = 1
        carb_count[first_daniel["Carb"]] = 1

    # STEP 2 — Fill the remaining slots
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
# Get ingredients for a specific meal
# ------------------------------------------------------------
def get_ingredients_for_meal(meal_name, ingredients_df):
    rows = ingredients_df[ingredients_df["Meal Name"] == meal_name]
    return [row["Ingredient"] for _, row in rows.iterrows()]


# ------------------------------------------------------------
# Build collated shopping list
# ------------------------------------------------------------
def build_shopping_list(meals, ingredients_df):
    counter = Counter()

    for meal in meals:
        meal_name = meal["Meal Name"]
        ingredients = get_ingredients_for_meal(meal_name, ingredients_df)

        for ingredient in ingredients:
            counter[ingredient] += 1

    return counter


# ------------------------------------------------------------
# Build email body
# ------------------------------------------------------------
def build_email_body(meals, ingredients_df):
    body = "<h2>Your Dinner Plan</h2>"

    for m in meals:
        body += f"<h3>{m['Meal Name']}</h3>"
        body += f"<p><b>Link:</b> <a href='{m['Link']}'>{m['Link']}</a><br>"
        body += f"<b>Method:</b> {m['Method']}<br>"
        body += f"<b>Notes:</b> {m['Notes']}</p>"

        ingredients = get_ingredients_for_meal(m["Meal Name"], ingredients_df)
        body += "<ul>"
        for ing in ingredients:
            body += f"<li>{ing}</li>"
        body += "</ul>"

    body += "<h2>Shopping List</h2>"
    shopping = build_shopping_list(meals, ingredients_df)

    body += "<ul>"
    for item, count in shopping.items():
        body += f"<li>{item} x{count}</li>"
    body += "</ul>"

    return body


# ------------------------------------------------------------
# Send email
# ------------------------------------------------------------
def send_email(to_email, subject, html_body, from_email, password):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    msg.attach(MIMEText(html_body, "html"))

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(from_email, password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()


# ------------------------------------------------------------
# Streamlit Web App
# ------------------------------------------------------------
def main():
    st.title("Weekly Dinner Picker 🍽️")
    st.write("Choose how many meals you want this week and generate a plan.")


    filename ="dinner options.xlsx"
    meals_df, ingredients_df = load_data(filename)

    # User chooses number of meals
    n = st.slider("Number of meals this week:", min_value=1, max_value=10, value=5)

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

        # Email section
        st.subheader("Email This Plan")
        to_email = st.text_input("Your email address")
        from_email = st.text_input("Sender Gmail address")
        password = st.text_input("Gmail App Password", type="password")

        if st.button("Send Email"):
            html_body = build_email_body(meals, ingredients_df)
            send_email(to_email, "Your Weekly Dinner Plan", html_body, from_email, password)
            st.success("Email sent successfully!")


if __name__ == "__main__":
    main()

