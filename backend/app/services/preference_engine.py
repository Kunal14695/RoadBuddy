"""
User Preference Engine — RoadBuddy
------------------------------------
Infers traveler preferences (budget tier, travel mode, accommodation style)
from past completed trips and maintains a snapshot in UserPreference table.
"""

from datetime import datetime
from collections import Counter
from sqlalchemy.orm import Session
from app.models.models import Trip, UserPreference


def classify_budget_tier(total_cost_inr: float) -> str:
    if total_cost_inr is None or total_cost_inr <= 0:
        return None
    if total_cost_inr < 5000:
        return "budget"
    elif total_cost_inr < 20000:
        return "mid"
    return "luxury"


def compute_user_preferences(db: Session, user_id: int) -> UserPreference:
    """
    Computes derived travel preferences for a user from their last 10 completed trips.
    Updates or creates a UserPreference record in DB.
    """
    past_trips = (
        db.query(Trip)
        .filter(Trip.user_id == user_id, Trip.status == "completed")
        .order_by(Trip.id.desc())
        .limit(10)
        .all()
    )

    if not past_trips:
        return None

    budget_tiers = [classify_budget_tier(t.total_cost_inr) for t in past_trips if t.total_cost_inr]
    budget_tiers = [b for b in budget_tiers if b is not None]

    travel_modes = [t.travel_mode for t in past_trips if t.travel_mode]

    most_common_budget = Counter(budget_tiers).most_common(1)[0][0] if budget_tiers else "mid"
    most_common_mode = Counter(travel_modes).most_common(1)[0][0] if travel_modes else "own_vehicle"

    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        pref = UserPreference(user_id=user_id)
        db.add(pref)

    pref.preferred_budget_tier = most_common_budget
    pref.preferred_travel_mode = most_common_mode
    pref.last_computed_at = datetime.utcnow()

    db.commit()
    db.refresh(pref)
    return pref
