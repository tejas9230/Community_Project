import os
import joblib
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from ai.preprocess import clean_text


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(BASE_DIR, "..", "dataset", "complaints.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")


# --------------------------------------------------
# Training Function
# --------------------------------------------------

def train_model():

    print("\n===================================")
    print("Loading Dataset...")
    print("===================================")

    df = pd.read_csv(DATASET_PATH)

    print(f"Total Complaints : {len(df)}")
    print(f"Categories       : {df['category'].nunique()}")

    # Clean complaint text
    df["complaint"] = df["complaint"].astype(str).apply(clean_text)

    X = df["complaint"]
    y = df["category"]

    # Split dataset
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    # TF-IDF
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1
    )

    X_train_vectorized = vectorizer.fit_transform(X_train)
    X_test_vectorized = vectorizer.transform(X_test)

    # Logistic Regression
    model = LogisticRegression(
        max_iter=1000,
        random_state=42
    )

    model.fit(X_train_vectorized, y_train)

    # Predictions
    predictions = model.predict(X_test_vectorized)

    accuracy = accuracy_score(y_test, predictions)

    # Save model
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    print("\n===================================")
    print(" AI MODEL TRAINED SUCCESSFULLY ")
    print("===================================")

    print(f"Dataset Size : {len(df)}")
    print(f"Training Set : {len(X_train)}")
    print(f"Testing Set  : {len(X_test)}")
    print(f"Categories   : {df['category'].nunique()}")

    print(f"\nAccuracy : {accuracy * 100:.2f}%")

    print("\nClassification Report")
    print("-----------------------------------")
    print(classification_report(y_test, predictions))

    print("Confusion Matrix")
    print("-----------------------------------")
    print(confusion_matrix(y_test, predictions))

    print("\nModel Saved      :", MODEL_PATH)
    print("Vectorizer Saved :", VECTORIZER_PATH)

    print("\n===================================")
    print(" Training Completed ")
    print("===================================\n")


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":
    train_model()