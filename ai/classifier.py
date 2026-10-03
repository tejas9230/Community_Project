"""
AI Complaint Prediction Engine

This module is responsible for:
1. Loading the trained AI model (with graceful fallback).
2. Multilingual & Transliteration NLP rule scoring (Hindi, Telugu, Tamil, Hinglish, Telgish, English).
3. Predicting complaint category, department, priority, and confidence.
4. Extracting Explainable AI (XAI) keywords and detecting Ambiguity.
"""

import os
import re

from ai.preprocess import clean_text
from models.department_mapping import CATEGORY_MAPPING
from utils.confidence import confidence_percentage

# --------------------------------------------------
# Multilingual NLP Rules & Keywords
# --------------------------------------------------

MULTILINGUAL_RULES = [
    {
        "category": "Water Supply",
        "department": "Water Supply",
        "priority": "High",
        "baseConf": 94,
        "strong": [
            r'water\s*supply', r'drinking\s*water', r'pipe\s*leak', r'pipeline', r'water\s*tank', r'tap\s*leak',
            r'पानी\s*का\s*पाइप', r'पानी\s*की\s*सप्लाई', r'पेयजल', r'नल\s*का\s*पानी', r'पानी\s*की\s*किल्लत', r'जल\s*आपूर्ति',
            r'మంచినీరు', r'నీటి\s*సమస్య', r'పైపు\s*లీక్', r'పైపులైన్', r'కుళాయి', r'నీరు\s*సరఫరా', r'నీళ్లు\s*రావట్లేదు',
            r'குடிநீர்', r'தண்ணீர்\s*குழாய்', r'குழாய்\s*உடைப்பு', r'தண்ணீர்\s*கசிவு', r'நீர்\s*விநியோகம்',
            r'paani\s*leak', r'paani\s*nahi', r'pani\s*supply', r'neellu\s*ravatledu', r'thanni\s*varala'
        ],
        "keywords": [
            r'\bwater\b', r'\bpipe\b', r'\bleak\b', r'\btap\b', r'\bsupply\b', r'\bchlorine\b', r'\bseepage\b',
            r'पानी', r'पेयजल', r'जलभराव', r'\bनल\b', r'पाइप', r'रिसाव',
            r'నీరు', r'నీళ్లు', r'నీళ్ల', r'పైపు', r'లీకేజీ', r'కుళాయి',
            r'தண்ணீர்', r'குடிநீர்', r'குழாய்', r'கசிவு',
            r'\bpaani\b', r'\bpani\b', r'\bneellu\b', r'\bneeru\b', r'\bthanni\b', r'\bthanneer\b'
        ],
        "tagKeywords": ['water', 'pipe', 'leak', 'tap', 'pipeline', 'पानी', 'पाइप', 'नल', 'నీరు', 'నీళ్లు', 'పైపు', 'కుళాయి', 'தண்ணீர்', 'குழாய்']
    },
    {
        "category": "Road Damage",
        "department": "Roads & Infrastructure",
        "priority": "High",
        "baseConf": 92,
        "strong": [
            r'pothole', r'road\s*damage', r'broken\s*road', r'asphalt\s*crack', r'road\s*crack', r'crater',
            r'गड्ढा', r'गड्ढे', r'टूटी\s*सड़क', r'सड़क\s*खराब', r'सड़क\s*पर\s*गड्ढा', r'खड्डा',
            r'గుంత', r'గుంతలు', r'రోడ్డు\s*పాడై', r'రోడ్డుపై\s*గుంత', r'తారు\s*రోడ్డు',
            r'குழி', r'பள்ளம்', r'சாலை\s*சேதம்', r'தார்\s*சாலை', r'உடைந்த\s*சாலை',
            r'guntalu', r'guntha', r'gaddha', r'gaddhe', r'sadak\s*kharab', r'road\s*lo\s*pedda\s*guntalu'
        ],
        "keywords": [
            r'\bpothole\b', r'\bpotholes\b', r'\bcrack\b', r'\basphalt\b', r'\btar\b', r'\bdivider\b', r'\bcrater\b', r'\bpavement\b',
            r'गड्ढा', r'गड्ढे', r'डामर', r'फुटपाथ',
            r'గుంత', r'గుంతలు', r'తారు', r'రహదారులు',
            r'குழி', r'பள்ளம்', r'தார்',
            r'\broad\b', r'\bhighway\b', r'सड़क', r'सड़क', r'రోడ్డు', r'రహదారి', r'சாலை'
        ],
        "tagKeywords": ['pothole', 'crack', 'asphalt', 'road', 'गड्ढा', 'सड़क', 'डामर', 'గుంతలు', 'రోడ్డు', 'రహదారి', 'குழி', 'சாலை']
    },
    {
        "category": "Street Light",
        "department": "Electricity & Street Lighting",
        "priority": "Medium",
        "baseConf": 90,
        "strong": [
            r'street\s*light', r'street\s*lamp', r'light\s*pole', r'streetlight', r'lamp\s*post',
            r'स्ट्रीट\s*लाइट', r'स्ट्रीटलाइट', r'खंभे\s*की\s*लाइट', r'लाइट\s*बंद', r'गली\s*की\s*बत्ती',
            r'వీధి\s*దీపం', r'వీధిదీపం', r'వీధి\s*లైట్', r'వీధి\s*దీపాలు', r'కరెంట్\s*స్తంభం',
            r'தெருவிளக்கு', r'மின்விளக்கு', r'விளக்கு\s*எரியவில்லை', r'தெரு\s*விளக்கு',
            r'veedhi\s*light', r'street\s*light\s*band', r'light\s*nahi\s*jal', r'velagatle'
        ],
        "keywords": [
            r'street\s*light', r'\blamp\b', r'\bbulb\b', r'\bdark\b', r'\blantern\b',
            r'बत्ती', r'अंधेरा', r'दीपक',
            r'లైట్లు', r'చీకటి', r'బల్బ్', r'దీపాలు',
            r'இருட்டு', r'இருட்டாக', r'பல்பு',
            r'\bandhera\b', r'\bcheekati\b', r'\biruttu\b'
        ],
        "tagKeywords": ['street light', 'lamp', 'bulb', 'dark', 'स्ट्रीट लाइट', 'अंधेरा', 'बत्ती', 'వీధి దీపం', 'లైట్లు', 'చీకటి', 'தெருவிளக்கு', 'இருட்டு']
    },
    {
        "category": "Electricity",
        "department": "Electricity & Street Lighting",
        "priority": "Critical",
        "baseConf": 96,
        "strong": [
            r'electric\s*shock', r'live\s*wire', r'wire\s*hanging', r'transformer\s*blast', r'power\s*outage', r'high\s*voltage',
            r'करंट\s*का\s*खतरा', r'तार\s*लटक', r'बिजली\s*का\s*तार', r'ट्रांसफार्मर\s*खराब', r'बिजली\s*गुल',
            r'కరెంట్\s*తీగలు', r'తీగలు\s*తెగి', r'షాక్\s*కొట్టే', r'ట్రాన్స్\s*ఫార్మర్', r'కరెంట్\s*పోయింది',
            r'மின்\s*கம்பி', r'கம்பி\s*அறுந்து', r'மின்வெட்டு', r'மின்சாரம்\s*இல்லை', r'மின்\s*கசிவு',
            r'live\s*wire', r'current\s*poyindi', r'bijli\s*chali\s*gayi', r'transformer\s*spark'
        ],
        "keywords": [
            r'\belectric\b', r'\bpower\b', r'\bwire\b', r'\bvoltage\b', r'\btransformer\b', r'\bshock\b', r'\bspark\b', r'\bfuse\b',
            r'बिजली', r'करंट', r'तार', r'ट्रांसफार्मर', r'विद्युत',
            r'కరెంట్', r'విద్యుత్', r'తీగలు', r'వైర్లు', r'షాక్',
            r'மின்சாரம்', r'மின்கம்பி', r'மின்மாற்றி',
            r'\bbijli\b', r'\bcurrent\b', r'\bminsaram\b'
        ],
        "tagKeywords": ['electric', 'power', 'wire', 'transformer', 'shock', 'बिजली', 'करंट', 'तार', 'కరెంట్', 'విద్యుత్', 'తీగలు', 'மின்சாரம்', 'மின்கம்பி']
    },
    {
        "category": "Garbage",
        "department": "Sanitation & Waste Management",
        "priority": "Medium",
        "baseConf": 88,
        "strong": [
            r'garbage\s*dump', r'waste\s*dump', r'garbage\s*pile', r'trash\s*bin', r'foul\s*smell',
            r'कचरे\s*का\s*ढेर', r'कचरा\s*पड़ा', r'कूड़े\s*का\s*ढेर', r'कूड़ादान\s*भर', r'बदबू\s*आ\s*रही',
            r'చెత్త\s*పేరుకుపోయి', r'చెత్త\s*కుప్పలు', r'దుర్వాసన', r'చెత్తకుండీ', r'చెత్త\s*డంపింగ్',
            r'குப்பைக்\s*குவியல்', r'குப்பை\s*கொட்டப்பட்டு', r'துர்நாற்றம்', r'குப்பை\s*தொட்டி',
            r'kachra\s*pada', r'chetta\s*dump', r'kuppai\s*kotti', r'dustbin\s*overflow'
        ],
        "keywords": [
            r'\bgarbage\b', r'\btrash\b', r'\bwaste\b', r'\bdump\b', r'\bbin\b', r'\blitter\b', r'\bdebris\b', r'\bsmell\b',
            r'कचरा', r'कूड़ा', r'कूड़ेदान', r'गंदगी', r'बदबू', r'सफाई', r'दुर्गंध',
            r'చెత్త', r'చెత్తకుండీ', r'వ్యర్థాలు', r'పరిశుభ్రత', r'కంపు',
            r'குப்பை', r'கழிவு', r'துப்புரவு',
            r'\bkachra\b', r'\bkooda\b', r'\bchetta\b', r'\bkuppai\b', r'\bbadboo\b'
        ],
        "tagKeywords": ['garbage', 'trash', 'waste', 'smell', 'कचरा', 'कूड़ा', 'बदबू', 'చెత్త', 'దుర్వాసన', 'குப்பை', 'துர்நாற்றம்']
    },
    {
        "category": "Drainage",
        "department": "Drainage & Sewage",
        "priority": "High",
        "baseConf": 91,
        "strong": [
            r'drainage\s*overflow', r'sewage\s*leak', r'open\s*manhole', r'gutter\s*clog', r'sewer\s*line',
            r'नाली\s*जाम', r'सीवर\s*जाम', r'गटर\s*का\s*पानी', r'नाली\s*का\s*पानी', r'सीवर\s*का\s*पानी', r'खुला\s*मैनहोल',
            r'మురుగు\s*కాలువ', r'మురుగు\s*కాల్వ', r'డ్రైనేజీ\s*సమస్య', r'డ్రైనేజి', r'పొంగిపొర్లుతోంది', r'మ్యాన్‌హోల్',
            r'சாக்கடை\s*அடைப்பு', r'கழிவுநீர்\s*சாலையில்', r'பாதாள\s*சாக்கடை', r'கழிவுநீர்\s*கால்வாய்',
            r'drainage\s*overflow', r'naali\s*jam', r'gutter\s*overflow', r'murugu\s*kaluva', r'saakadai\s*adaippu'
        ],
        "keywords": [
            r'\bdrain\b', r'\bdrainage\b', r'\bsewage\b', r'\bgutter\b', r'\bmanhole\b', r'\bclog\b', r'\bsewer\b',
            r'नाली', r'सीवर', r'गटर', r'सीवेज',
            r'కాలువ', r'మురుగుకాల్వ', r'మురుగునీరు', r'డ్రైనేజీ',
            r'சாக்கடை', r'கழிவுநீர்',
            r'\bnaali\b', r'\bgatar\b', r'\bkaluva\b', r'\bmurugu\b', r'\bsaakadai\b'
        ],
        "tagKeywords": ['drainage', 'sewage', 'gutter', 'manhole', 'नाली', 'सीवर', 'गटर', 'కాలువ', 'మురుగు', 'డ్రైనేజీ', 'சாக்கடை', 'கழிவுநீர்']
    },
    {
        "category": "Animal",
        "department": "Animal Control",
        "priority": "High",
        "baseConf": 89,
        "strong": [
            r'stray\s*dog', r'dog\s*bite', r'monkey\s*menace', r'rabid\s*dog', r'pack\s*of\s*dogs',
            r'आवारा\s*कुत्ते', r'कुत्तों\s*का\s*झुंड', r'कुत्ते\s*काटते', r'बंदरों\s*का\s*आतंक', r'पागल\s*कुत्ता',
            r'పిచ్చి\s*కుక్కలు', r'కుక్కల\s*దాడి', r'పిల్లలను\s*కరుస్తున్నాయి', r'కోతుల\s*బాధ', r'కుక్కలు\s*తిరుగుతున్నాయి',
            r'தெரு\s*நாய்கள்', r'நாய்கள்\s*தொல்லை', r'மக்களை\s*கடிக்கிறது', r'குரங்கு\s*தொல்லை',
            r'stray\s*dog', r'kukkalu\s*karustunnayi', r'kutte\s*kaat', r'naai\s*thollai'
        ],
        "keywords": [
            r'\bdog\b', r'\bdogs\b', r'\bstray\b', r'\bmonkey\b', r'\banimal\b', r'\bbite\b', r'\bcow\b', r'\bcattle\b', r'\bsnake\b',
            r'कुत्ता', r'कुत्ते', r'बंदर', r'गाय', r'सांप', r'जानवर', r'पशु',
            r'కుక్క', r'కుక్కలు', r'కోతులు', r'ఆవులు', r'పశువులు', r'పాము',
            r'நாய்', r'நாய்கள்', r'குரங்கு', r'மாடு', r'பாம்பு',
            r'\bkutta\b', r'\bkutte\b', r'\bkukkalu\b', r'\bnaai\b', r'\bbandar\b'
        ],
        "tagKeywords": ['dog', 'stray animal', 'monkey', 'कुत्ता', 'आवारा कुत्ते', 'बंदर', 'కుక్కలు', 'పిచ్చి కుక్కలు', 'కోతులు', 'நாய்', 'குரங்கு']
    },
    {
        "category": "Traffic",
        "department": "Traffic & Public Safety",
        "priority": "Medium",
        "baseConf": 87,
        "strong": [
            r'traffic\s*jam', r'traffic\s*signal', r'signal\s*not\s*working', r'heavy\s*traffic', r'traffic\s*congestion',
            r'ट्रैफिक\s*जाम', r'सिग्नल\s*काम\s*नहीं', r'सिग्नल\s*खराब', r'यातायात\s*जाम', r'चौराहे\s*पर\s*जाम',
            r'ట్రాఫిక్\s*జామ్', r'ట్రాఫిక్\s*సిగ్నల్', r'సిగ్నల్\s*పనిచేయడం\s*లేదు', r'రద్దీగా\s*ఉంది',
            r'போக்குவரத்து\s*நெரிசல்', r'சிக்னல்\s*வேலை\s*செய்யவில்லை', r'வாகன\s*நெரிசல்',
            r'traffic\s*jam', r'signal\s*panicheyatle', r'heavy\s*jam'
        ],
        "keywords": [
            r'traffic', r'\bsignal\b', r'\bjam\b', r'\bparking\b', r'\bcongestion\b', r'\baccident\b', r'\bgridlock\b',
            r'ट्रैफिक', r'सिग्नल', r'यातायात', r'\bजाम\b',
            r'ట్రాఫిక్', r'సిగ్నల్', r'\bజామ్\b', r'రద్దీ',
            r'போக்குவரத்து', r'சிக்னல்',
            r'\bjam\b', r'\braddi\b'
        ],
        "tagKeywords": ['traffic', 'signal', 'congestion', 'जाम', 'ट्रैफिक', 'सिग्नल', 'ట్రాఫిక్', 'జామ్', 'సిగ్నల్', 'போக்குவரத்து', 'சிக்னல்']
    },
    {
        "category": "Parks & Green Spaces",
        "department": "Parks & Green Spaces",
        "priority": "Low",
        "baseConf": 86,
        "strong": [
            r'fallen\s*tree', r'tree\s*branch', r'park\s*maintenance', r'playground\s*broken',
            r'पेड़\s*गिर\s*गया', r'पार्क\s*की\s*सफाई', r'पौधे\s*सूख',
            r'చెట్టు\s*కూలిపోయింది', r'పార్క్\s*నిర్వహణ', r'ఆటస్థలం',
            r'மரம்\s*விழுந்தது', r'பூங்கா\s*பராமரிப்பு',
            r'ped\s*gir\s*gaya', r'chettu\s*koolindi'
        ],
        "keywords": [
            r'\bpark\b', r'\bbench\b', r'\btree\b', r'\bplayground\b', r'\bgrass\b', r'\bgarden\b', r'\bpruning\b',
            r'पार्क', r'पेड़', r'बगीचा', r'घास',
            r'పార్క్', r'చెట్లు', r'చెట్టు', r'తోట',
            r'பூங்கா', r'மரம்',
            r'\bgarden\b', r'\bped\b', r'\bmaram\b'
        ],
        "tagKeywords": ['park', 'tree', 'garden', 'पार्क', 'पेड़', 'बगीचा', 'పార్క్', 'చెట్లు', 'பூங்கா', 'மரம்']
    },
    {
        "category": "Public Property",
        "department": "Public Property Maintenance",
        "priority": "Low",
        "baseConf": 85,
        "strong": [
            r'bus\s*stop\s*damaged', r'public\s*property', r'broken\s*fence', r'wall\s*collapse',
            r'बस\s*स्टॉप\s*टूटा', r'सार्वजनिक\s*संपत्ति', r'दीवार\s*गिर',
            r'బస్టాప్\s*పాడైంది', r'ప్రభుత్వ\s*ఆస్తి', r'గోడ\s*కూలింది',
            r'பேருந்து\s*நிறுத்தம்\s*சேதம்', r'பொது\s*சொத்து',
            r'bus\s*stop\s*damage', r'wall\s*crack'
        ],
        "keywords": [
            r'\bproperty\b', r'\bbuilding\b', r'\bfence\b', r'\bwall\b', r'\bvandalism\b', r'bus\s*stop\b',
            r'संपत्ति', r'दीवार', r'इमारत',
            r'ఆస్తి', r'భవనం', r'గోడ',
            r'சொத்து', r'சுவர்',
            r'\bbus\s*stop\b'
        ],
        "tagKeywords": ['bus stop', 'public property', 'wall', 'सार्वजनिक संपत्ति', 'दीवार', 'ప్రభుత్వ ఆస్తి', 'గోడ', 'பொது சொத்து']
    }
]

# --------------------------------------------------
# Optional Model and Vectorizer Loader
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")

model = None
vectorizer = None

try:
    import joblib
    if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)
except Exception:
    model = None
    vectorizer = None


def predict_multilingual_rule(text):
    desc = text.lower()
    scores = []

    for r in MULTILINGUAL_RULES:
        score = 0
        found_tags = []

        for sp in r["strong"]:
            if re.search(sp, desc, re.IGNORECASE):
                score += 12

        for kw in r["keywords"]:
            if re.search(kw, desc, re.IGNORECASE):
                is_loc = any(x in kw for x in ['road', 'highway', 'सड़क', 'రోడ్డు', 'சாலை'])
                score += 1 if is_loc else 3

        for tag in r["tagKeywords"]:
            if tag.lower() in desc and tag not in found_tags:
                found_tags.append(tag)

        if score > 0:
            scores.append({
                "category": r["category"],
                "department": r["department"],
                "priority": r["priority"],
                "baseConf": r["baseConf"],
                "score": score,
                "keywords": found_tags
            })

    if not scores:
        return None

    scores.sort(key=lambda x: (x["score"], x["baseConf"]), reverse=True)
    top = scores[0]

    is_ambiguous = False
    secondary_category = None
    secondary_department = None
    margin = 100.0

    if len(scores) > 1:
        top2 = scores[1]
        diff_score = top["score"] - top2["score"]
        margin = max(5.0, min(100.0, float(diff_score * 8)))
        if diff_score <= 5 and top2["score"] >= 4:
            is_ambiguous = True
            secondary_category = top2["category"]
            secondary_department = top2["department"]

    conf = min(99, top["baseConf"] + min(5, top["score"] // 3))
    kws = top["keywords"][:5]

    if not kws:
        kws = [w for w in re.split(r'[\s,.;:!?।]+', desc) if len(w) > 3 and w not in ['with', 'have', 'from', 'this', 'that', 'near', 'there']][:4]

    return {
        "success": True,
        "category": top["category"],
        "department": top["department"],
        "priority": top["priority"],
        "confidence": conf,
        "keywords": kws,
        "is_ambiguous": is_ambiguous,
        "secondary_category": secondary_category,
        "secondary_department": secondary_department,
        "margin": margin,
        "score": top["score"]
    }


# --------------------------------------------------
# Prediction Function
# --------------------------------------------------

def predict_complaint(complaint_text):
    """
    Predict complaint category with Explainable AI keywords and Ambiguity detection.
    Supports English, Hindi, Telugu, Tamil, and Hinglish/Telgish.
    """
    if not complaint_text or not complaint_text.strip():
        return {
            "success": False,
            "message": "Complaint cannot be empty."
        }

    # 1. Run Multilingual Rule Engine
    rule_res = predict_multilingual_rule(complaint_text)
    if rule_res and rule_res.get("score", 0) >= 3:
        return {
            "success": True,
            "category": rule_res["category"],
            "department": rule_res["department"],
            "priority": rule_res["priority"],
            "confidence": rule_res["confidence"],
            "keywords": rule_res["keywords"],
            "is_ambiguous": rule_res["is_ambiguous"],
            "secondary_category": rule_res["secondary_category"],
            "secondary_department": rule_res["secondary_department"],
            "margin": rule_res["margin"]
        }

    # 2. Try ML Model if available
    cleaned_text = clean_text(complaint_text)
    if model is not None and vectorizer is not None:
        try:
            vector = vectorizer.transform([cleaned_text])
            if vector.nnz > 0:
                probabilities = model.predict_proba(vector)[0]
                classes = model.classes_
                sorted_indices = probabilities.argsort()[::-1]

                top1_idx = sorted_indices[0]
                predicted_category = classes[top1_idx]
                top1_prob = float(probabilities[top1_idx])
                confidence = confidence_percentage(top1_prob)

                keywords = []
                try:
                    feature_names = vectorizer.get_feature_names_out()
                    coo = vector.tocoo()
                    sorted_items = sorted(zip(coo.col, coo.data), key=lambda x: x[1], reverse=True)
                    keywords = [str(feature_names[idx]) for idx, score in sorted_items[:5]]
                except Exception:
                    keywords = [w for w in cleaned_text.split() if len(w) > 3][:5]

                is_ambiguous = False
                secondary_category = None
                secondary_department = None
                margin = 100.0

                if len(sorted_indices) > 1:
                    top2_idx = sorted_indices[1]
                    top2_cat = classes[top2_idx]
                    top2_prob = float(probabilities[top2_idx])
                    margin = round((top1_prob - top2_prob) * 100, 1)

                    if margin <= 18.0 and top2_prob >= 0.15:
                        is_ambiguous = True
                        secondary_category = top2_cat
                        sec_details = CATEGORY_MAPPING.get(top2_cat)
                        if sec_details:
                            secondary_department = sec_details.get("department")

                details = CATEGORY_MAPPING.get(predicted_category)
                if details:
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
        except Exception:
            pass

    # 3. Fallback: If weak rule match exists
    if rule_res:
        return {
            "success": True,
            "category": rule_res["category"],
            "department": rule_res["department"],
            "priority": rule_res["priority"],
            "confidence": rule_res["confidence"],
            "keywords": rule_res["keywords"],
            "is_ambiguous": rule_res["is_ambiguous"],
            "secondary_category": rule_res["secondary_category"],
            "secondary_department": rule_res["secondary_department"],
            "margin": rule_res["margin"]
        }

    # 4. Default Others
    return {
        "success": True,
        "category": "Others",
        "department": "Others",
        "priority": "Medium",
        "confidence": 85,
        "keywords": [w for w in cleaned_text.split() if len(w) > 3][:4],
        "is_ambiguous": False,
        "secondary_category": None,
        "secondary_department": None,
        "margin": 100.0
    }