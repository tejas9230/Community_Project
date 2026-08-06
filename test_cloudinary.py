import os
from dotenv import load_dotenv
load_dotenv()

import cloudinary
import cloudinary.uploader
from PIL import Image
import io

# Cloudinary auto-configures from CLOUDINARY_URL env var
print("Cloud name:", cloudinary.config().cloud_name)
print("API Key set:", bool(cloudinary.config().api_key))

# Upload a tiny test image
img = Image.new("RGB", (50, 50), color=(96, 165, 250))
buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

result = cloudinary.uploader.upload(
    buf,
    folder="project_k_test",
    public_id="connection_test",
    overwrite=True,
    resource_type="image"
)

print("Upload OK!")
print("URL:", result.get("secure_url"))

# Clean up test image
cloudinary.uploader.destroy("project_k_test/connection_test")
print("Test image deleted. Cloudinary is ready!")
