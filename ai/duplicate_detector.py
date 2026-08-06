from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class DuplicateComplaintDetector:

    def __init__(self):

        print("Loading Sentence-BERT model...")

        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        print("Model Loaded Successfully.\n")


    # -----------------------------------------
    # Find Similar Complaints
    # -----------------------------------------

    def find_similar_complaints(
        self,
        new_complaint,
        existing_complaints,
        top_k=3
    ):

        if len(existing_complaints) == 0:

            return []

        # Encode new complaint

        new_embedding = self.model.encode(
            [new_complaint]
        )

        # Encode database complaints

        existing_embeddings = self.model.encode(
            existing_complaints
        )

        # Calculate similarity

        similarities = cosine_similarity(
            new_embedding,
            existing_embeddings
        )[0]

        results = []

        for i, score in enumerate(similarities):

            results.append({

                "complaint":
                    existing_complaints[i],

                "similarity":
                    round(float(score) * 100, 2)

            })

        # Highest similarity first

        results.sort(
            key=lambda x: x["similarity"],
            reverse=True
        )

        results = [
            item
           for item in results
           if item["similarity"] >= 60
        ]

        return results[:top_k]


    # -----------------------------------------
    # Backward Compatibility
    # -----------------------------------------

    def check_duplicate(
        self,
        new_complaint,
        existing_complaints,
        threshold=80
    ):

        similar = self.find_similar_complaints(
            new_complaint,
            existing_complaints,
            top_k=1
        )

        if len(similar) == 0:

            return None

        best = similar[0]

        return {

            "duplicate":
                best["similarity"] >= threshold,

            "similarity":
                best["similarity"] / 100,

            "matched_complaint":
                best["complaint"]

        }


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    detector = DuplicateComplaintDetector()

    complaints = [

        "Street light near bus stop is not working",

        "Garbage has not been collected for three days",

        "Water pipeline burst near market",

        "Road has a large pothole near school",

        "Large pothole beside government school",

        "Deep crack on road near school gate"

    ]

    new_complaint = "Huge pothole near school"

    results = detector.find_similar_complaints(
        new_complaint,
        complaints
    )

    print("\nTop Similar Complaints\n")

    for i, item in enumerate(results, start=1):

        print(f"{i}. {item['complaint']}")

        print(f"   Similarity : {item['similarity']}%\n")