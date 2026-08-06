"""
Priority Calculator

Calculates the effective priority of a complaint
based on:

1. AI Predicted Priority
2. Number of active related complaints
"""

PRIORITY_LEVELS = {

    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4

}


def calculate_priority(ai_priority, related_reports):

    priority = ai_priority

    if related_reports >= 6:

        priority = "Critical"

    elif related_reports >= 4:

        if ai_priority == "Medium":
            priority = "High"

        elif ai_priority == "High":
            priority = "Critical"

    elif related_reports >= 2:

        if ai_priority == "Low":
            priority = "Medium"

        elif ai_priority == "Medium":
            priority = "High"

    return priority