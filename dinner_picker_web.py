import streamlit as st
import pandas as pd
import random
from collections import Counter
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# ------------------------------------------------------------
# Load spreadsheet safely (works on Streamlit Cloud)
# ------------------------------------------------------------
def get_excel_path():
    return os.path.join(os.path.dirname(__file__), "dinners.xlsx")


def load_data():
    excel_path = get_excel_path()
    meals_df = pd.read_excel(excel_path, sheet_name="Meals")
    ingredients_df = pd.read_excel(excel_path, sheet_name="Ingredients")
    return meals_df, ingredients_df


# ------------------------------------------------------------
# Choose meals with weighted randomness + Daniel rule
# ------------------------------------------------------------
def choose_meals(df, n):
    chosen = []
    meat_count = {}
    carb_count = {}

    weighted_options = []
    for _, row in df.iterrows():
        weight = int(row["Rating"])
        weighted_options.extend([row.to_dict()] * weight)

    random.shuffle(weighted_options)

    # Ensure at least one Daniel meal
    daniel_meals = [
        m for m in weighted_options
        if str(m["Daniel Meal"]).strip().lower() == "yes"
    ]

    if daniel_meals:
        first_daniel = daniel_meals[0]
        chosen.append(first_daniel)
        meat_count[first_daniel["Meat"]] = 1
        carb_count[first_daniel["Carb"]] = 1

    # Fill remaining slots
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
