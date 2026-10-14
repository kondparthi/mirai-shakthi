"""Small, safe condition language for requirement rules (no eval).

A condition is a JSON object:
  {"all": [cond, ...]}    every child true
  {"any": [cond, ...]}    at least one child true
  {"not": cond}
  {"field": "turnover_band", "gte": 2}
  {"field": "business_type", "in": ["manufacturing", "trading"]}
  {"field": "registrations", "contains": "gst"}
  {"field": "channels", "contains_any": ["online", "export"]}
  {"field": "employees", "lt": 10}
  {"field": "sector", "eq": "food"}
An empty / null condition is always true.
"""
from typing import Any

OPS = {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "contains", "not_contains", "contains_any", "is_set"}


def _get(profile: dict, field: str) -> Any:
    return profile.get(field)


def evaluate(cond: dict | None, profile: dict) -> bool:
    if not cond:
        return True
    if "all" in cond:
        return all(evaluate(c, profile) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, profile) for c in cond["any"])
    if "not" in cond:
        return not evaluate(cond["not"], profile)
    field = cond.get("field")
    if not field:
        raise ValueError(f"Condition needs a field: {cond}")
    value = _get(profile, field)
    for op in OPS & cond.keys():
        target = cond[op]
        if op == "is_set":
            ok = (value not in (None, "", [])) == bool(target)
        elif value is None:
            ok = False
        elif op == "eq":
            ok = value == target
        elif op == "ne":
            ok = value != target
        elif op == "in":
            ok = value in target
        elif op == "not_in":
            ok = value not in target
        elif op == "gt":
            ok = value > target
        elif op == "gte":
            ok = value >= target
        elif op == "lt":
            ok = value < target
        elif op == "lte":
            ok = value <= target
        elif op == "contains":
            ok = target in (value or [])
        elif op == "not_contains":
            ok = target not in (value or [])
        elif op == "contains_any":
            ok = bool(set(target) & set(value or []))
        else:  # pragma: no cover
            ok = False
        if not ok:
            return False
    return True


def validate(cond: dict | None) -> None:
    """Raise ValueError if a condition is malformed (used by the admin rule builder)."""
    if not cond:
        return
    if "all" in cond or "any" in cond:
        for c in cond.get("all", cond.get("any")):
            validate(c)
        return
    if "not" in cond:
        validate(cond["not"])
        return
    if "field" not in cond or not (OPS & cond.keys()):
        raise ValueError(f"Invalid condition: {cond}")
