"""
Central mapping for AI predicted complaint categories.

Every AI module will use this file.

Do NOT hardcode departments or priorities anywhere else.
"""

CATEGORY_MAPPING = {

    "Road Damage": {
        "department": "Roads & Infrastructure",
        "priority": "High"
    },

    "Water Supply": {
        "department": "Water Supply",
        "priority": "High"
    },

    "Street Light": {
        "department": "Electricity & Street Lighting",
        "priority": "Medium"
    },

    "Electricity": {
        "department": "Electricity & Street Lighting",
        "priority": "Critical"
    },

    "Garbage": {
        "department": "Sanitation & Waste Management",
        "priority": "Medium"
    },

    "Drainage": {
        "department": "Drainage Department",
        "priority": "High"
    },

    "Obstruction": {
        "department": "Roads & Infrastructure",
        "priority": "High"
    },

    "Public Property": {
        "department": "Municipal Administration",
        "priority": "Medium"
    },

    "Animal": {
        "department": "Animal Control",
        "priority": "Medium"
    },

    "Traffic": {
        "department": "Traffic Police",
        "priority": "High"
    }

}