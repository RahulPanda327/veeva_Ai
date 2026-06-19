"""ML model: predict response → Rx conversion success rate for Module 3.

Uses a scikit-learn LogisticRegression trained on historical transcript outcomes.
Model is trained during the weekly Celery batch refresh and cached to Redis.
"""
import json
import logging
from typing import Dict, List, Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder

from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

_MODEL_CACHE_KEY = "ml:conversion_optimizer:model"
_ENCODER_CACHE_KEY = "ml:conversion_optimizer:encoder"


def _build_feature_vector(
    objection_type: str,
    hcp_segment: str,
    call_count: int,
    response_source: str,
    le: LabelEncoder,
) -> np.ndarray:
    """Encode categorical features + numeric features into a flat array."""
    try:
        ot_enc = le.transform([objection_type])[0]
    except ValueError:
        ot_enc = -1
    seg_map = {"A": 3, "B": 2, "C": 1}
    seg_enc = seg_map.get(hcp_segment, 0)
    mlr_flag = 1 if "MLR" in (response_source or "") else 0
    return np.array([[ot_enc, seg_enc, min(call_count, 50), mlr_flag]])


def train_conversion_model(training_data: List[Dict]) -> Optional[LogisticRegression]:
    """Train LR model on historical objection-response-outcome data.

    Each record: {objection_type, hcp_segment, call_count, response_source, converted}
    """
    if len(training_data) < 10:
        logger.warning("Insufficient training data (%d rows). Skipping model training.", len(training_data))
        return None

    le = LabelEncoder()
    obj_types = [r["objection_type"] for r in training_data]
    le.fit(obj_types)

    X, y = [], []
    for r in training_data:
        X.append(
            _build_feature_vector(
                r["objection_type"],
                r.get("hcp_segment", "B"),
                r.get("call_count", 1),
                r.get("response_source", ""),
                le,
            )[0]
        )
        y.append(int(r["converted"]))

    model = LogisticRegression(max_iter=500, random_state=42)
    model.fit(np.array(X), y)

    # Cache encoder labels alongside model metadata
    cache_set(_ENCODER_CACHE_KEY, le.classes_.tolist(), ttl=86400 * 7)
    logger.info("Conversion optimizer model trained on %d samples.", len(training_data))
    return model


def predict_success_rate(
    model: LogisticRegression,
    le_classes: List[str],
    objection_type: str,
    hcp_segment: str,
    call_count: int,
    response_source: str,
) -> float:
    """Return predicted probability of Rx conversion after using this response."""
    le = LabelEncoder()
    le.classes_ = np.array(le_classes)
    features = _build_feature_vector(objection_type, hcp_segment, call_count, response_source, le)
    prob = model.predict_proba(features)[0][1]
    return round(float(prob), 4)
