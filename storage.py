"""
storage.py — Image storage abstraction
Supports local file system (dev) and Cloudinary (production).

Usage:
    from storage import save_image, get_image_url

Set CLOUDINARY_URL in .env for production:
    CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
"""

import os
from werkzeug.utils import secure_filename

CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")
USE_CLOUDINARY  = bool(CLOUDINARY_URL)

UPLOAD_FOLDER   = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file_obj, prefix: str = "complaint") -> str | None:
    """
    Save an uploaded file and return a path/URL string.

    - Local:      saves to static/uploads/, returns relative path  e.g. "uploads/complaint_abc.jpg"
    - Cloudinary: uploads to cloud, returns secure Cloudinary URL
    Returns None if no file or invalid extension.
    """
    if not file_obj or file_obj.filename == "":
        return None

    filename = secure_filename(file_obj.filename)
    if not allowed_file(filename):
        return None

    if USE_CLOUDINARY:
        return _save_to_cloudinary(file_obj, prefix)
    else:
        return _save_locally(file_obj, filename, prefix)


def _save_locally(file_obj, filename: str, prefix: str) -> str:
    """Save to static/uploads/ and return path string."""
    import uuid
    ext      = filename.rsplit(".", 1)[1].lower()
    new_name = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, new_name)
    file_obj.save(save_path)
    return f"uploads/{new_name}"


def _save_to_cloudinary(file_obj, prefix: str) -> str:
    """Upload to Cloudinary and return secure URL."""
    import cloudinary
    import cloudinary.uploader

    # cloudinary is configured from CLOUDINARY_URL env var automatically
    result = cloudinary.uploader.upload(
        file_obj,
        folder="project_k",
        public_id=f"{prefix}_{os.urandom(4).hex()}",
        overwrite=False,
        resource_type="image"
    )
    return result.get("secure_url", "")


def get_image_url(path_or_url: str) -> str:
    """
    Convert a stored path/url to a usable <img src> URL.
    - Local path like "uploads/foo.jpg"  → "/static/uploads/foo.jpg"
    - Cloudinary URL (starts with https) → returned as-is
    """
    if not path_or_url:
        return ""
    if path_or_url.startswith("http"):
        return path_or_url
    # Strip any leading slash and prefix with /static/
    return "/static/" + path_or_url.lstrip("/")
