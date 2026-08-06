"""
CV Comparator — Before vs After Image Analysis Engine  (Upgraded)

Tasks:
1. check_image_consistency()   — validates citizen image vs complaint category
2. calculate_resolution_score() — compares before/after with:
     * pHash fraud detection  (same photo -> 0%)
     * SSIM structural score
     * Colour histogram distance
     * Edge / ORB feature matching
"""

import cv2
import numpy as np
from PIL import Image
import os

def _load_image(path):
    try:
        img = Image.open(path).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        return None

def _load_pil(path):
    try:
        return Image.open(path).convert("L")
    except Exception:
        return None

def _phash(pil_img, hash_size=16):
    img  = pil_img.resize((hash_size, hash_size), Image.LANCZOS)
    arr  = np.array(img, dtype=float)
    return arr > arr.mean()

def _hash_similarity(h1, h2):
    return 1.0 - np.count_nonzero(h1 != h2) / h1.size

def _ssim(a_gray, b_gray):
    try:
        from skimage.metrics import structural_similarity
        score, _ = structural_similarity(a_gray, b_gray, full=True)
        return float(score)
    except ImportError:
        a = a_gray.astype(float); b = b_gray.astype(float)
        num = np.sum((a - a.mean()) * (b - b.mean()))
        den = np.sqrt(np.sum((a - a.mean())**2) * np.sum((b - b.mean())**2)) + 1e-8
        return float(num / den)

def _orb_match_ratio(b_gray, a_gray):
    try:
        orb = cv2.ORB_create(500)
        kp1, des1 = orb.detectAndCompute(b_gray, None)
        kp2, des2 = orb.detectAndCompute(a_gray, None)
        if des1 is None or des2 is None or len(des1) < 5 or len(des2) < 5:
            return 0.5
        bf      = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        good    = [m for m in matches if m.distance < 50]
        return len(good) / max(len(kp1), len(kp2))
    except Exception:
        return 0.5

def _hist(img):
    h = cv2.calcHist([img], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
    cv2.normalize(h, h)
    return h

_yolo_model = None
def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _yolo_model = YOLO(os.path.join(base, "yolov8n.pt"))
    return _yolo_model

CATEGORY_HINTS = {
    "Animal":       ["dog","cat","bird","horse","sheep","cow","elephant","bear","zebra","giraffe"],
    "Traffic":      ["car","truck","motorcycle","bus","bicycle","traffic light"],
    "Street Light": ["traffic light"],
    "Road Damage":  ["car","truck","bus"],
    "Garbage":      ["bottle","cup","chair","suitcase","backpack"],
}

def check_image_consistency(image_path, predicted_category):
    try:
        if not image_path or not os.path.exists(image_path):
            return {"consistent":True,"detected_objects":[],"message":"No image to check","needs_flag":False}
        model   = _get_yolo()
        img_arr = _load_image(image_path)
        if img_arr is None:
            return {"consistent":True,"detected_objects":[],"message":"Could not load image","needs_flag":False}
        results  = model(img_arr, verbose=False)
        detected = []
        for r in results:
            for box in r.boxes:
                if float(box.conf[0]) >= 0.35:
                    detected.append(r.names[int(box.cls[0])])
        expected = CATEGORY_HINTS.get(predicted_category, [])
        if not expected:
            return {"consistent":True,"detected_objects":detected,"message":"Category not verifiable by CV","needs_flag":False}
        matched = [o for o in detected if o in expected]
        if matched:
            return {"consistent":True,"detected_objects":detected,"message":f"Image verified: {', '.join(set(matched))} detected","needs_flag":False}
        if not detected:
            return {"consistent":True,"detected_objects":[],"message":"Image unclear but accepted","needs_flag":False}
        return {"consistent":False,"detected_objects":detected,
                "message":f"Image shows {', '.join(set(detected[:3]))} but complaint is '{predicted_category}'. Flagged for review.","needs_flag":True}
    except Exception as e:
        return {"consistent":True,"detected_objects":[],"message":f"CV check skipped ({str(e)[:60]})","needs_flag":False}

def calculate_resolution_score(before_path, after_path):
    try:
        before_cv  = _load_image(before_path)
        after_cv   = _load_image(after_path)
        before_pil = _load_pil(before_path)
        after_pil  = _load_pil(after_path)
        if before_cv is None: return _err("Could not load before image")
        if after_cv  is None: return _err("Could not load after image")

        W, H = 640, 480
        b = cv2.resize(before_cv,(W,H)); a = cv2.resize(after_cv,(W,H))
        b_gray = cv2.cvtColor(b,cv2.COLOR_BGR2GRAY)
        a_gray = cv2.cvtColor(a,cv2.COLOR_BGR2GRAY)

        # pHash fraud detection
        if before_pil and after_pil:
            if _hash_similarity(_phash(before_pil), _phash(after_pil)) >= 0.95:
                return {"score":0.0,"verdict":"Fraud Detected","new_status":"In Progress",
                        "message":"Same photo submitted as resolution. Please upload an actual after-photo.",
                        "pixel_change":0,"color_change":0,"edge_change":0,
                        "ssim":1.0,"orb_match":1.0,"fraud":True,"location_ok":True,"error":None}

        ssim_score  = _ssim(b_gray, a_gray)
        ssim_change = 1.0 - ssim_score
        hist_dist   = float(cv2.compareHist(_hist(b),_hist(a),cv2.HISTCMP_BHATTACHARYYA))
        edge_diff   = float(np.mean(cv2.absdiff(cv2.Canny(b_gray,50,150), cv2.Canny(a_gray,50,150))))/255.0
        orb_ratio   = _orb_match_ratio(b_gray, a_gray)
        location_ok = orb_ratio >= 0.05

        combined  = ssim_change*0.40 + hist_dist*0.35 + edge_diff*0.25
        score     = round(max(0.0, min(100.0, ((combined-0.04)/0.21)*100)), 1)
        if not location_ok:
            score = round(score * 0.75, 1)

        if score >= 75:   verdict,new_status,msg = "Verified",   "Resolved",     f"Resolution verified ({score}%). Issue appears fixed."
        elif score >= 40: verdict,new_status,msg = "Needs Review","Under Review", f"Partial change detected ({score}%). Admin will review."
        else:             verdict,new_status,msg = "Not Resolved","In Progress",  f"Insufficient change ({score}%). Please re-inspect."

        if not location_ok:
            msg += " Warning: Before and after photos may be from different locations."

        return {"score":score,"verdict":verdict,"new_status":new_status,"message":msg,
                "pixel_change":round(ssim_change*100,1),"color_change":round(hist_dist*100,1),
                "edge_change":round(edge_diff*100,1),"ssim":round(ssim_score,3),
                "orb_match":round(orb_ratio,3),"fraud":False,"location_ok":location_ok,"error":None}
    except Exception as e:
        return _err(str(e))

def _err(msg):
    return {"score":0,"verdict":"Error","new_status":"In Progress","message":msg,
            "pixel_change":0,"color_change":0,"edge_change":0,"ssim":0,"orb_match":0,
            "fraud":False,"location_ok":True,"error":msg}
