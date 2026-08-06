"""
AI Complaint Prediction Engine

This module is responsible for:
1. Loading the trained AI model.
2. Cleaning complaint text.
3. Predicting complaint category.
4. Calculating confidence.
5. Returning department and priority.
"""

import os
import joblib

from ai.preprocess import clean_text
from models.department_mapping import CATEGORY_MAPPING
from utils.confidence import confidence_percentage


# --------------------------------------------------
# Load Model and Vectorizer (only once)
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)


# --------------------------------------------------
# Prediction Function
# --------------------------------------------------

def predict_complaint(complaint_text):
    """
    Predict complaint category.

    Parameters:
        complaint_text (str)

    Returns:
        dict
    """

    # Validate input
    if not complaint_text or not complaint_text.strip():
        return {
            "success": False,
            "message": "Complaint cannot be empty."
        }

    # Clean text
    cleaned_text = clean_text(complaint_text)

    # Convert to TF-IDF
    vector = vectorizer.transform([cleaned_text])

    # Predict category
    predicted_category = model.predict(vector)[0]

    # Predict confidence
    probability = model.predict_proba(vector).max()
    confidence = confidence_percentage(probability)

    # Get mapping
    details = CATEGORY_MAPPING.get(predicted_category)

    # Safety check
    if details is None:
        return {
            "success": False,
            "message": f"No mapping found for category: {predicted_category}"
        }

    return {
        "success": True,
        "category": predicted_category,
        "department": details["department"],
        "priority": details["priority"],
        "confidence": confidence
    }