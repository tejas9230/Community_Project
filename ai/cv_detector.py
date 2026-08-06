from ultralytics import YOLO
import os

print("=" * 50)
print("Current Working Directory:")
print(os.getcwd())
print("=" * 50)

image_path = os.path.join("static", "uploads", "road.jpg")

print("Image Path :", image_path)
print("Exists     :", os.path.exists(image_path))

print("\nLoading YOLO...")

model = YOLO("yolov8n.pt")

print("YOLO Loaded Successfully!")

if os.path.exists(image_path):

    results = model(image_path)

    print("\nDetection Finished Successfully!")

else:

    print("\nERROR: Image not found!")