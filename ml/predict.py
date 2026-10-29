import os
import sys
import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from ml.preprocess import validate_features, get_risk_label
from ml.train import ensure_model_ready

_model = None

def get_model():
    """Returns singleton instance of the trained XGBoost model."""
    global _model
    if _model is None:
        if os.path.exists(Config.MODEL_PATH):
            _model = joblib.load(Config.MODEL_PATH)
        else:
            _model = ensure_model_ready()
    return _model

def get_recommendations(risk_level):
    """Returns actionable safety recommendations tailored to the predicted risk level."""
    if risk_level == "High Risk":
        return [
            "CRITICAL WARNING: Immediate threat of flash flooding and street waterlogging.",
            "Move to elevated or higher ground immediately.",
            "Do not drive or walk through flood waters — 15cm of flowing water can knock you down.",
            "Disconnect electrical main breakers and turn off gas lines if water enters building.",
            "Keep emergency contact numbers and go-bag (documents, water, medicine, torch) handy.",
            "Follow municipal disaster management directives and evacuation orders promptly."
        ]
    elif risk_level == "Medium Risk":
        return [
            "ADVISORY: Significant risk of water stagnation and localized flooding in low-lying zones.",
            "Avoid basement parking lots and low-lying underpasses.",
            "Clear outdoor storm drains and ensure water outlets around premises are unblocked.",
            "Monitor ongoing municipal and meteorological weather bulletins.",
            "Charge mobile devices, flashlights, and store potable drinking water.",
            "Postpone non-essential travel in areas prone to seasonal inundation."
        ]
    else: # Low Risk
        return [
            "NORMAL CONDITIONS: Flood risk is minimal under prevailing weather parameters.",
            "Municipal drainage networks are expected to operate within standard capacity.",
            "Routine seasonal maintenance of rooftop gutters and drainage gullies is recommended.",
            "Stay informed of 24-hour weather forecast changes during rainy seasons."
        ]

def predict_flood_risk(weather_data):
    """
    Performs inference on meteorological inputs.
    Args:
        weather_data: dict or DataFrame with keys [rainfall, humidity, temperature, wind_speed, pressure]
    Returns:
        dict containing:
            - risk_level: 'Low Risk' | 'Medium Risk' | 'High Risk'
            - risk_class: 0 | 1 | 2
            - probability: float (percentage 0.0 - 100.0)
            - probabilities: dict of class percentages
            - recommendations: list of strings
            - features: dict of processed values
    """
    model = get_model()
    df_features = validate_features(weather_data)

    # Predict class
    prediction = model.predict(df_features)[0]
    risk_class = int(prediction)
    risk_level = get_risk_label(risk_class)

    # Predict probabilities
    prob_array = model.predict_proba(df_features)[0]
    probabilities = {
        "Low Risk": round(float(prob_array[0]) * 100, 2),
        "Medium Risk": round(float(prob_array[1]) * 100, 2),
        "High Risk": round(float(prob_array[2]) * 100, 2)
    }

    primary_probability = probabilities[risk_level]

    return {
        "risk_level": risk_level,
        "risk_class": risk_class,
        "probability": primary_probability,
        "probabilities": probabilities,
        "recommendations": get_recommendations(risk_level),
        "features": df_features.iloc[0].to_dict()
    }
