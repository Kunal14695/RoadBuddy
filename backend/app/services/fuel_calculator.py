"""
Fuel & Toll Calculator Service
-------------------------------
Provides real NHAI toll costs for major highway corridors, city-specific fuel prices,
and realistic fallback calculations for road trips across India.
"""

# Real retail fuel prices in India (₹ per litre/unit) by city and fuel type
# Sources: IOCL & state petroleum dealers (July 2026 update)
FUEL_PRICES = {
    "default": {
        "petrol":   104.0,
        "diesel":    90.0,
        "cng":       85.0,   # per kg
        "electric":   8.5,   # per kWh
    },
    "delhi": {
        "petrol":   102.12,
        "diesel":    95.20,
        "cng":       80.0,
        "electric":   8.0,
    },
    "mumbai": {
        "petrol":   111.21,
        "diesel":    97.83,
        "cng":       89.0,
        "electric":   9.0,
    },
    "bengaluru": {
        "petrol":   110.89,
        "diesel":    98.80,
        "cng":       86.0,
        "electric":   8.5,
    },
    "chennai": {
        "petrol":   108.01,
        "diesel":    99.66,
        "cng":       84.5,
        "electric":   8.0,
    },
    "kolkata": {
        "petrol":   113.51,
        "diesel":    99.82,
        "cng":       87.0,
        "electric":   8.5,
    },
    "jaipur": {
        "petrol":   112.66,
        "diesel":    97.78,
        "cng":       85.0,
        "electric":   8.0,
    },
    "udaipur": {
        "petrol":   113.20,
        "diesel":    98.30,
        "cng":       86.0,
        "electric":   8.2,
    }
}

# Realistic average NHAI toll rates (₹ per km) by vehicle category
TOLL_RATE_PER_KM = {
    "two_wheeler":  0.50,
    "car":          1.80,
    "suv":          2.20,
    "van":          2.80,
}

# Real one-way toll costs (₹) for a standard LMV/car on popular highway corridors in India
REAL_TOLLS = {
    ("delhi", "jaipur"): 400.0,
    ("delhi", "agra"): 450.0,          # Yamuna Expressway
    ("mumbai", "pune"): 320.0,         # Mumbai-Pune Expressway
    ("bengaluru", "mysuru"): 355.0,    # Bengaluru-Mysuru Expressway
    ("delhi", "mumbai"): 1450.0,       # Delhi-Mumbai Expressway sections combined
    ("jaipur", "udaipur"): 480.0,
    ("delhi", "chandigarh"): 380.0,
    ("bengaluru", "chennai"): 520.0,
    ("hyderabad", "bengaluru"): 720.0,
    ("chennai", "pondicherry"): 180.0,
    ("ahmedabad", "mumbai"): 550.0,
    ("pune", "goa"): 420.0,
    ("lucknow", "delhi"): 780.0,
    ("lucknow", "agra"): 600.0
}


def calculate_fuel_cost(
    distance_km: float,
    mileage_kmpl: float,
    fuel_type: str,
    city: str = "Jaipur",
) -> dict:
    city_key = (city or "default").lower().strip()
    city_prices = FUEL_PRICES.get(city_key, FUEL_PRICES["default"])
    price = city_prices.get(fuel_type, FUEL_PRICES["default"][fuel_type])
    
    # Ensure mileage is positive to avoid ZeroDivisionError
    safe_mileage = max(mileage_kmpl, 0.1)
    units_required = distance_km / safe_mileage
    cost = units_required * price
    return {
        "units_required": round(units_required, 2),
        "cost_inr": round(cost, 2),
        "price_per_unit": price,
        "fuel_type": fuel_type,
        "city": city or "Jaipur",
    }


def calculate_toll_cost(
    distance_km: float,
    vehicle_category: str,
    origin: str = None,
    destination: str = None
) -> float:
    # If route-specific info is available, look up real toll data
    if origin and destination:
        key = (origin.lower().strip(), destination.lower().strip())
        reverse_key = (destination.lower().strip(), origin.lower().strip())
        
        toll_val = REAL_TOLLS.get(key) or REAL_TOLLS.get(reverse_key)
        if toll_val is not None:
            # Scale toll price according to vehicle category compared to LMV/car (base 1.0)
            scale = 1.0
            if vehicle_category == "two_wheeler":
                scale = 0.40
            elif vehicle_category == "suv":
                scale = 1.25
            elif vehicle_category == "van":
                scale = 1.60
            return round(toll_val * scale, 2)
            
    # Fallback to distance-based estimation
    rate = TOLL_RATE_PER_KM.get(vehicle_category, 1.80)
    return round(distance_km * rate, 2)


def estimate_distance(origin: str, destination: str) -> float:
    """
    Mock distance estimation for popular Indian routes.
    """
    mock_distances = {
        ("jaipur", "udaipur"):       400.0,
        ("jaipur", "delhi"):         280.0,
        ("mumbai", "pune"):          150.0,
        ("delhi", "agra"):           230.0,
        ("bengaluru", "mysuru"):     145.0,
        ("chennai", "pondicherry"):  160.0,
        ("delhi", "mumbai"):        1420.0,
        ("delhi", "chandigarh"):     245.0,
        ("bengaluru", "chennai"):    350.0,
        ("hyderabad", "bengaluru"):  575.0,
        ("ahmedabad", "mumbai"):     525.0,
        ("pune", "goa"):             450.0,
        ("lucknow", "delhi"):        530.0,
        ("lucknow", "agra"):         335.0,
    }
    key = (origin.lower().strip(), destination.lower().strip())
    reverse_key = (destination.lower().strip(), origin.lower().strip())
    return mock_distances.get(key) or mock_distances.get(reverse_key) or 300.0


def build_fuel_calc_response(
    origin: str,
    destination: str,
    vehicle: dict,   # {fuel_type, mileage_kmpl, category}
    include_return: bool = False,
) -> dict:
    distance = estimate_distance(origin, destination)
    
    mileage = vehicle.get("mileage_kmpl")
    if mileage is None:
        mileage = 15.0  # sensible default mileage
    fuel_type = vehicle.get("fuel_type", "petrol")
    category = vehicle.get("category", "car")

    fuel = calculate_fuel_cost(
        distance,
        mileage,
        fuel_type,
        city=origin
    )
    toll = calculate_toll_cost(distance, category, origin, destination)

    total_one_way = round(fuel["cost_inr"] + toll, 2)
    total_return  = round(total_one_way * 2, 2) if include_return else None

    return {
        "distance_km": distance,
        "fuel_litres_required": fuel["units_required"],
        "fuel_cost_inr": fuel["cost_inr"],
        "toll_cost_inr": toll,
        "total_one_way_inr": total_one_way,
        "total_with_return_inr": total_return,
        "fuel_price_per_litre": fuel["price_per_unit"],
        "city": origin,
    }


# ── Vehicle Fuel Range & Gap Warnings ─────────────────────────────────────────

def calculate_vehicle_range_km(vehicle) -> float:
    """
    Estimate how far the vehicle can travel on a full tank/charge,
    using mileage_kmpl and assumed fuel tank / battery capacity.
    """
    fuel_type = getattr(vehicle, "fuel_type", None) or (vehicle.get("fuel_type") if isinstance(vehicle, dict) else "petrol")
    fuel_type = (fuel_type or "petrol").lower().strip()

    if fuel_type in ["electric", "ev"]:
        est_range = getattr(vehicle, "estimated_range_km", None) or (vehicle.get("estimated_range_km") if isinstance(vehicle, dict) else None)
        return float(est_range or 250.0)

    mileage = getattr(vehicle, "mileage_kmpl", None) or (vehicle.get("mileage_kmpl") if isinstance(vehicle, dict) else None)
    mileage = float(mileage or 15.0)

    category = getattr(vehicle, "category", None) or (vehicle.get("category") if isinstance(vehicle, dict) else "car")
    category = (category or "car").lower().strip()

    assumed_tank_liters = 15.0 if category == "two_wheeler" else 40.0
    return round(mileage * assumed_tank_liters, 1)


def find_fuel_gap_warnings(
    distance_km: float,
    fuel_stations: list,
    vehicle_range_km: float,
    is_ev: bool = False
) -> list:
    """
    Flags any gap along the route that exceeds a safety-margin percentage (70%)
    of the vehicle's estimated maximum range.
    """
    SAFETY_MARGIN = 0.70
    safe_gap_km = vehicle_range_km * SAFETY_MARGIN
    station_label = "EV charging station" if is_ev else "fuel station"

    warnings = []

    if not fuel_stations:
        if distance_km > safe_gap_km:
            warnings.append({
                "gap_distance_km": round(distance_km, 1),
                "message": f"No verified {station_label} found on this {round(distance_km)} km stretch - ensure a full {'charge' if is_ev else 'tank'} before departure."
            })
        return warnings

    # Sort stations by distance along route if provided
    checkpoints = sorted(
        fuel_stations,
        key=lambda s: s.get("distance_along_route_km", 0.0) if isinstance(s, dict) else getattr(s, "distance_along_route_km", 0.0)
    )

    prev_distance = 0.0
    for station in checkpoints:
        dist_along = station.get("distance_along_route_km", 0.0) if isinstance(station, dict) else getattr(station, "distance_along_route_km", 0.0)
        gap = dist_along - prev_distance
        if gap > safe_gap_km:
            warnings.append({
                "gap_start_km": round(prev_distance, 1),
                "gap_end_km": round(dist_along, 1),
                "gap_distance_km": round(gap, 1),
                "message": f"No {station_label} for {round(gap)} km - refuel before this stretch."
            })
        prev_distance = dist_along

    # Final gap check from last station to destination
    final_gap = distance_km - prev_distance
    if final_gap > safe_gap_km:
        warnings.append({
            "gap_start_km": round(prev_distance, 1),
            "gap_end_km": round(distance_km, 1),
            "gap_distance_km": round(final_gap, 1),
            "message": f"Final {round(final_gap)} km stretch has no verified {station_label}s - ensure sufficient range."
        })

    return warnings

