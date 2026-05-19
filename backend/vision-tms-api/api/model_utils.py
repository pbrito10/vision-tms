from __future__ import annotations

import json
from typing import Any


def model_dump(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "json"):
        return json.loads(model.json())
    return model.dict()
