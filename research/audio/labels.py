LABELS = ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]

LABEL_ALIASES = {
    "chainsaw": "chainsaw",
    "chain_saw": "chainsaw",
    "hand_saw": "chainsaw",
    "saw": "chainsaw",
    "gunshot": "gunshot",
    "gun_shot": "gunshot",
    "gunfire": "gunshot",
    "fireworks": "gunshot",
    "vehicle": "vehicle",
    "engine": "vehicle",
    "engine_idling": "vehicle",
    "car_horn": "vehicle",
    "siren": "vehicle",
    "helicopter": "vehicle",
    "airplane": "vehicle",
    "train": "vehicle",
    "fire_crackle": "fire_crackle",
    "crackling_fire": "fire_crackle",
    "fire": "fire_crackle",
    "background": "background_unknown",
    "background_unknown": "background_unknown",
    "unknown": "background_unknown",
}


def canonical_label(label: str) -> str:
    normalized = label.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized not in LABEL_ALIASES:
        raise ValueError(f"Unsupported audio label: {label}")
    return LABEL_ALIASES[normalized]
