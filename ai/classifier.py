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
    Predict complaint category with Explainable AI keywords and Ambiguity detection.

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

    # Predict category and class probabilities
    probabilities = model.predict_proba(vector)[0]
    classes = model.classes_
    sorted_indices = probabilities.argsort()[::-1]

    top1_idx = sorted_indices[0]
    predicted_category = classes[top1_idx]
    top1_prob = float(probabilities[top1_idx])
    confidence = confidence_percentage(top1_prob)

    # Extract top keywords (Explainable AI)
    keywords = []
    try:
        feature_names = vectorizer.get_feature_names_out()
        coo = vector.tocoo()
        sorted_items = sorted(zip(coo.col, coo.data), key=lambda x: x[1], reverse=True)
        keywords = [str(feature_names[idx]) for idx, score in sorted_items[:5]]
    except Exception:
        keywords = [w for w in cleaned_text.split() if len(w) > 3][:5]

    # Detect ambiguity (e.g. Road vs Water conflict)
    is_ambiguous = False
    secondary_category = None
    secondary_department = None
    margin = 100.0

    if len(sorted_indices) > 1:
        top2_idx = sorted_indices[1]
        top2_cat = classes[top2_idx]
        top2_prob = float(probabilities[top2_idx])
        margin = round((top1_prob - top2_prob) * 100, 1)

        # Ambiguity threshold: margin <= 18% and top2 prob >= 15%
        if margin <= 18.0 and top2_prob >= 0.15:
            is_ambiguous = True
            secondary_category = top2_cat
            sec_details = CATEGORY_MAPPING.get(top2_cat)
            if sec_details:
                secondary_department = sec_details.get("department")

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
        "confidence": confidence,
        "keywords": keywords,
        "is_ambiguous": is_ambiguous,
        "secondary_category": secondary_category,
        "secondary_department": secondary_department,
        "margin": margin
    }