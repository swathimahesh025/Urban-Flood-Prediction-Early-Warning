import numpy as np
import pandas as pd

# The exact feature ordering expected by the model
FEATURE_NAMES = ["rainfall", "humidity", "temperature", "wind_speed", "pressure"]

RISK_LABELS = {
    0: "Low Risk",
    1: "Medium Risk",
    2: "High Risk"
}

def validate_features(data):
    """
    Validates and formats input weather parameters into a DataFrame matching FEATURE_NAMES.
    Accepts either a dict or a pandas DataFrame.
    """
    if isinstance(data, dict):
        # Extract features with sensible defaults if missing
        row = {
            "rainfall": float(data.get("rainfall", 0.0)),
            "humidity": float(data.get("humidity", 50.0)),
            "temperature": float(data.get("temperature", 25.0)),
            "wind_speed": float(data.get("wind_speed", 5.0)),
            "pressure": float(data.get("pressure", 1013.0)),
        }
        df = pd.DataFrame([row], columns=FEATURE_NAMES)
    elif isinstance(data, pd.DataFrame):
        for col in FEATURE_NAMES:
            if col not in data.columns:
                raise ValueError(f"Missing required feature column: {col}")
        df = data[FEATURE_NAMES].copy()
    elif isinstance(data, (list, np.ndarray)):
        arr = np.array(data)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != len(FEATURE_NAMES):
            raise ValueError(f"Expected {len(FEATURE_NAMES)} features, got {arr.shape[1]}")
        df = pd.DataFrame(arr, columns=FEATURE_NAMES)
    else:
        raise TypeError(f"Unsupported data type for feature validation: {type(data)}")

    # Basic range sanitization
    df["rainfall"] = df["rainfall"].clip(lower=0.0, upper=500.0)
    df["humidity"] = df["humidity"].clip(lower=0.0, upper=100.0)
    df["temperature"] = df["temperature"].clip(lower=-20.0, upper=60.0)
    df["wind_speed"] = df["wind_speed"].clip(lower=0.0, upper=150.0)
    df["pressure"] = df["pressure"].clip(lower=850.0, upper=1100.0)

    return df

def get_risk_label(class_index):
    """Maps class integer (0, 1, 2) to string representation."""
    return RISK_LABELS.get(int(class_index), "Unknown Risk")
