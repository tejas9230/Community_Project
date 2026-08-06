import cv2
import os

image_path = os.path.join("static", "uploads", "road.jpg")

print("Image Path:", image_path)
print("Exists:", os.path.exists(image_path))

img = cv2.imread(image_path)

print("Image Object:", img)

if img is None:
    print("❌ OpenCV could not read the image.")
else:
    print("✅ Image loaded successfully.")
    print("Shape:", img.shape)