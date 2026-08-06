def confidence_percentage(probability):
    """
    Convert ML probability into a Python float percentage.
    """

    return float(round(probability * 100, 2))