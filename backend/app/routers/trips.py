from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.services.trip_chatbot import chat_with_roadbuddy
from typing import Optional
from sqlalchemy.orm import Session
from app.services.waypoint_suggester import suggest_waypoints
from app.schemas.schemas import TripCreate, TripOut, TravelMode
from app.services.ai_planner import generate_itinerary
from app.core.auth import get_current_user
from app.services.route_safety import analyze_route_safety
from app.core.database import get_db
from app.models.models import Trip, TripStop, Vehicle
from app.services.trip_recommender import get_trip_recommendations

router = APIRouter()


@router.post("/generate", response_model=TripOut, status_code=201)
async def create_trip(
    data: TripCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate an AI-powered road trip itinerary."""

    if data.travel_mode == TravelMode.own_vehicle:
        if not data.vehicle_id:
            raise HTTPException(
                status_code=400,
                detail="vehicle_id is required for own vehicle mode"
            )
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == int(data.vehicle_id),
            Vehicle.user_id == int(current_user["user_id"])
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        vehicle_info = {
            "fuel_type":    vehicle.fuel_type,
            "category":     vehicle.category,
            "mileage_kmpl": vehicle.mileage_kmpl,
        }
    else:
        vehicle_info = {}

    try:
        trip_out = await generate_itinerary(data, vehicle_info)

        trip = Trip(
            user_id            = int(current_user["user_id"]),
            vehicle_id         = int(data.vehicle_id) if data.vehicle_id else None,
            origin             = data.origin,
            destination        = data.destination,
            origin_lat         = data.origin_lat,
            origin_lon         = data.origin_lon,
            destination_lat    = data.destination_lat,
            destination_lon    = data.destination_lon,
            start_date         = data.start_date,
            end_date           = data.end_date,
            budget_inr         = data.budget_inr,
            travel_mode        = data.travel_mode,
            group_type         = data.group_type,
            num_people         = data.num_people,
            fuel_cost_inr      = trip_out.fuel_cost_inr,
            toll_cost_inr      = trip_out.toll_cost_inr,
            transport_fare_inr = trip_out.transport_fare_inr,
            return_fare_inr    = trip_out.return_fare_inr,
            hotel_cost_inr     = trip_out.hotel_cost_inr,
            food_cost_inr      = trip_out.food_cost_inr,
            total_cost_inr     = trip_out.total_estimated_cost_inr,
            ai_summary         = trip_out.ai_summary,
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)

        for stop in trip_out.stops:
            db_stop = TripStop(
                trip_id    = trip.id,
                day        = stop.day,
                time_slot  = stop.time_slot,
                place_name = stop.place_name,
                place_type = stop.place_type,
                description = stop.description,
                estimated_cost_inr = stop.estimated_cost_inr,
            )
            db.add(db_stop)
        db.commit()

        trip_out.id = str(trip.id)
        trip_out.start_date = trip.start_date
        trip_out.end_date = trip.end_date
        trip_out.group_type = trip.group_type
        trip_out.num_people = trip.num_people
        trip_out.budget_inr = trip.budget_inr
        trip_out.origin_lat = trip.origin_lat
        trip_out.origin_lon = trip.origin_lon
        trip_out.destination_lat = trip.destination_lat
        trip_out.destination_lon = trip.destination_lon
        return trip_out

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my", response_model=list[TripOut])
def list_my_trips(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all trips for the logged-in user."""
    trips = db.query(Trip).filter(
        Trip.user_id == int(current_user["user_id"])
    ).all()

    return [
        TripOut(
            id                       = str(t.id),
            origin                   = t.origin,
            destination              = t.destination,
            origin_lat               = t.origin_lat,
            origin_lon               = t.origin_lon,
            destination_lat          = t.destination_lat,
            destination_lon          = t.destination_lon,
            travel_mode              = t.travel_mode,
            total_distance_km        = 0,
            stops                    = [],
            fuel_cost_inr            = t.fuel_cost_inr,
            toll_cost_inr            = t.toll_cost_inr,
            transport_fare_inr       = t.transport_fare_inr,
            return_fare_inr          = t.return_fare_inr,
            hotel_cost_inr           = t.hotel_cost_inr,
            food_cost_inr            = t.food_cost_inr,
            total_estimated_cost_inr = t.total_cost_inr,
            ai_summary               = t.ai_summary or "",
            start_date               = t.start_date,
            end_date                 = t.end_date,
            group_type               = t.group_type,
            num_people               = t.num_people,
            budget_inr               = t.budget_inr,
        )
        for t in trips
    ]


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single trip with all stops."""
    trip = db.query(Trip).filter(
        Trip.id == int(trip_id),
        Trip.user_id == int(current_user["user_id"])
    ).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    raw_stops = db.query(TripStop).filter(TripStop.trip_id == trip.id).all()
    slot_order = {"morning": 0, "afternoon": 1, "evening": 2, "night": 3}
    stops = sorted(raw_stops, key=lambda s: (s.day, slot_order.get((s.time_slot or "").lower(), 4)))

    from app.schemas.schemas import ItineraryStop
    stop_list = [
        ItineraryStop(
            day         = s.day,
            time_slot   = s.time_slot,
            place_name  = s.place_name,
            place_type  = s.place_type,
            description = s.description or "",
            estimated_cost_inr = s.estimated_cost_inr or 0.0,
        )
        for s in stops
    ]

    return TripOut(
        id                       = str(trip.id),
        origin                   = trip.origin,
        destination              = trip.destination,
        origin_lat               = trip.origin_lat,
        origin_lon               = trip.origin_lon,
        destination_lat          = trip.destination_lat,
        destination_lon          = trip.destination_lon,
        travel_mode              = trip.travel_mode,
        total_distance_km        = 0,
        stops                    = stop_list,
        fuel_cost_inr            = trip.fuel_cost_inr,
        toll_cost_inr            = trip.toll_cost_inr,
        transport_fare_inr       = trip.transport_fare_inr,
        return_fare_inr          = trip.return_fare_inr,
        hotel_cost_inr           = trip.hotel_cost_inr,
        food_cost_inr            = trip.food_cost_inr,
        total_estimated_cost_inr = trip.total_cost_inr,
        ai_summary               = trip.ai_summary or "",
        start_date               = trip.start_date,
        end_date                 = trip.end_date,
        group_type               = trip.group_type,
        num_people               = trip.num_people,
        budget_inr               = trip.budget_inr,
    )


@router.put("/{trip_id}", response_model=TripOut)
async def update_trip(
    trip_id: str,
    data: TripCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing trip and regenerate its itinerary."""
    trip = db.query(Trip).filter(
        Trip.id == int(trip_id),
        Trip.user_id == int(current_user["user_id"])
    ).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if data.travel_mode == TravelMode.own_vehicle:
        if not data.vehicle_id:
            raise HTTPException(
                status_code=400,
                detail="vehicle_id is required for own vehicle mode"
            )
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == int(data.vehicle_id),
            Vehicle.user_id == int(current_user["user_id"])
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        vehicle_info = {
            "fuel_type":    vehicle.fuel_type,
            "category":     vehicle.category,
            "mileage_kmpl": vehicle.mileage_kmpl,
        }
    else:
        vehicle_info = {}

    try:
        # Check if any planning detail has changed
        detail_changed = (
            trip.start_date != data.start_date or
            trip.end_date != data.end_date or
            trip.origin.lower() != data.origin.lower() or
            trip.destination.lower() != data.destination.lower() or
            trip.travel_mode != data.travel_mode or
            trip.budget_inr != data.budget_inr or
            trip.num_people != data.num_people or
            trip.group_type != data.group_type or
            trip.vehicle_id != (int(data.vehicle_id) if data.vehicle_id else None)
        )

        if detail_changed:
            from app.models.models import HotelBooking, Booking, TrainBooking, BusBooking, FlightBooking, ProviderBooking, FoodOrder
            
            # 1. Clear Hotel Bookings
            db.query(HotelBooking).filter(
                HotelBooking.user_id == trip.user_id,
                HotelBooking.check_in_date == trip.start_date
            ).delete()
            
            # 2. Clear Transit Bookings
            db.query(Booking).filter(
                Booking.user_id == trip.user_id,
                Booking.travel_date == trip.start_date
            ).delete()
            db.query(TrainBooking).filter(
                TrainBooking.user_id == trip.user_id,
                TrainBooking.travel_date == trip.start_date
            ).delete()
            db.query(BusBooking).filter(
                BusBooking.user_id == trip.user_id,
                BusBooking.travel_date == trip.start_date
            ).delete()
            db.query(FlightBooking).filter(
                FlightBooking.user_id == trip.user_id,
                FlightBooking.travel_date == trip.start_date
            ).delete()
            
            # 3. Clear Cab Bookings
            db.query(ProviderBooking).filter(
                ProviderBooking.user_id == trip.user_id,
                ProviderBooking.travel_date == trip.start_date
            ).delete()
            
            # 4. Clear Food Orders
            db.query(FoodOrder).filter(
                FoodOrder.user_id == trip.user_id
            ).delete()

        trip_out = await generate_itinerary(data, vehicle_info)

        # Update trip fields
        trip.vehicle_id         = int(data.vehicle_id) if data.vehicle_id else None
        trip.origin             = data.origin
        trip.destination        = data.destination
        trip.origin_lat         = data.origin_lat
        trip.origin_lon         = data.origin_lon
        trip.destination_lat    = data.destination_lat
        trip.destination_lon    = data.destination_lon
        trip.start_date         = data.start_date
        trip.end_date           = data.end_date
        trip.budget_inr         = data.budget_inr
        trip.travel_mode        = data.travel_mode.value if hasattr(data.travel_mode, 'value') else data.travel_mode
        trip.group_type         = data.group_type.value if hasattr(data.group_type, 'value') else data.group_type
        trip.num_people         = data.num_people
        trip.fuel_cost_inr      = trip_out.fuel_cost_inr
        trip.toll_cost_inr      = trip_out.toll_cost_inr
        trip.transport_fare_inr = trip_out.transport_fare_inr
        trip.return_fare_inr    = trip_out.return_fare_inr
        trip.hotel_cost_inr     = trip_out.hotel_cost_inr
        trip.food_cost_inr      = trip_out.food_cost_inr
        trip.total_cost_inr     = trip_out.total_estimated_cost_inr
        trip.ai_summary         = trip_out.ai_summary

        # Clear old stops
        db.query(TripStop).filter(TripStop.trip_id == trip.id).delete()

        # Add new stops
        for stop in trip_out.stops:
            db_stop = TripStop(
                trip_id    = trip.id,
                day        = stop.day,
                time_slot  = stop.time_slot,
                place_name = stop.place_name,
                place_type = stop.place_type,
                description = stop.description,
                estimated_cost_inr = stop.estimated_cost_inr,
            )
            db.add(db_stop)
        
        db.commit()
        db.refresh(trip)

        trip_out.id = str(trip.id)
        trip_out.start_date = trip.start_date
        trip_out.end_date = trip.end_date
        trip_out.group_type = trip.group_type
        trip_out.num_people = trip.num_people
        trip_out.budget_inr = trip.budget_inr
        trip_out.origin_lat = trip.origin_lat
        trip_out.origin_lon = trip.origin_lon
        trip_out.destination_lat = trip.destination_lat
        trip_out.destination_lon = trip.destination_lon
        return trip_out
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trip_id}/cost")
def get_trip_cost(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full cost breakdown for a trip."""
    trip = db.query(Trip).filter(
        Trip.id == int(trip_id),
        Trip.user_id == int(current_user["user_id"])
    ).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.travel_mode == TravelMode.own_vehicle:
        return {
            "trip_id":     trip_id,
            "travel_mode": trip.travel_mode,
            "breakdown": {
                "fuel_cost_inr":  trip.fuel_cost_inr,
                "toll_cost_inr":  trip.toll_cost_inr,
                "hotel_cost_inr": trip.hotel_cost_inr,
                "food_cost_inr":  trip.food_cost_inr,
            },
            "grand_total_inr": trip.total_cost_inr,
        }
    else:
        return {
            "trip_id":     trip_id,
            "travel_mode": trip.travel_mode,
            "breakdown": {
                "going_fare_inr":  trip.transport_fare_inr,
                "return_fare_inr": trip.return_fare_inr,
                "hotel_cost_inr":  trip.hotel_cost_inr,
                "food_cost_inr":   trip.food_cost_inr,
            },
            "grand_total_inr": trip.total_cost_inr,
        }


@router.delete("/{trip_id}", status_code=204)
def delete_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a trip and all its stops."""
    trip = db.query(Trip).filter(
        Trip.id == int(trip_id),
        Trip.user_id == int(current_user["user_id"])
    ).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    db.query(TripStop).filter(TripStop.trip_id == trip.id).delete()
    db.delete(trip)
    db.commit()



class WaypointRequest(BaseModel):
    origin: str
    destination: str
    preferences: Optional[list[str]] = []
    travel_mode: Optional[str] = "own_vehicle"
    num_people: Optional[int] = 2
    group_type: Optional[str] = "friends"


@router.post("/suggest-waypoints")
async def get_waypoint_suggestions(request: WaypointRequest):
    """
    AI-powered waypoint suggestions between origin and destination.
    Returns hidden gems, dhabas, viewpoints, and must-visit stops.
    """
    try:
        result = await suggest_waypoints(
            origin=request.origin,
            destination=request.destination,
            preferences=request.preferences,
            travel_mode=request.travel_mode,
            num_people=request.num_people,
            group_type=request.group_type,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))




def get_optional_user(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header
    else:
        token = request.cookies.get("access_token")
        
    if not token:
        return None
        
    try:
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        if user_id:
            return {"user_id": user_id}
    except Exception:
        pass
    return None


def build_user_context(user_id: int, db: Session) -> str:
    from app.models.models import User, Vehicle, Trip, Booking, HotelBooking, TrainBooking, BusBooking, FlightBooking, ProviderBooking
    from app.services.transport_service import get_transport_option_by_id, get_transit_stops_and_amenities
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return ""
        
    lines = []
    lines.append(f"User Name: {user.name}")
    lines.append(f"User Email: {user.email}")
    
    # Vehicles
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user_id).limit(5).all()
    if vehicles:
        lines.append("User Vehicles:")
        for v in vehicles:
            lines.append(f"- Vehicle: {v.name} ({v.category}, Fuel: {v.fuel_type}, Mileage: {v.mileage_kmpl} kmpl)")
            
    # Trips
    trips = db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.id.desc()).limit(5).all()
    if trips:
        lines.append("User Trips:")
        for t in trips:
            lines.append(f"- Trip: {t.origin} to {t.destination} ({t.start_date} to {t.end_date or 'N/A'}), Travel Mode: {t.travel_mode}, Budget: INR {t.budget_inr}, Total Estimated Cost: INR {t.total_cost_inr}")

    # Hotel Bookings
    hotel_bookings = db.query(HotelBooking).filter(HotelBooking.user_id == user_id, HotelBooking.status != "cancelled").order_by(HotelBooking.id.desc()).limit(5).all()
    if hotel_bookings:
        lines.append("User Hotel Bookings:")
        for hb in hotel_bookings:
            hotel_name = hb.hotel.name if (hb.hotel) else "Hotel"
            hotel_city = hb.hotel.city if (hb.hotel) else "Unknown"
            hotel_amenities = hb.hotel.amenities if (hb.hotel and hb.hotel.amenities) else "WiFi, AC"
            comp_list = ["Complimentary Welcome Drink"]
            if "restaurant" in hotel_amenities.lower() or "breakfast" in hotel_amenities.lower() or "pool" in hotel_amenities.lower():
                comp_list.append("Complimentary Buffet Breakfast")
            comp_str = ", ".join(comp_list)
            lines.append(
                f"- Hotel Booking: {hotel_name} in {hotel_city}. Check-in: {hb.check_in_date}, Check-out: {hb.check_out_date}. Rooms: {hb.num_rooms}, Guests: {hb.num_guests}. Status: {hb.status}. Price: INR {hb.total_price_inr}. Included Amenities: {hotel_amenities}. Complimentary Inclusions: {comp_str}."
            )
            
    # Train Bookings
    train_bookings = db.query(TrainBooking).filter(TrainBooking.user_id == user_id, TrainBooking.status != "cancelled").order_by(TrainBooking.id.desc()).limit(5).all()
    if train_bookings:
        lines.append("User Train Bookings:")
        for tb in train_bookings:
            train_name = tb.train.train_name if (tb.train) else "Train"
            train_num = tb.train.train_number if (tb.train) else "N/A"
            origin = tb.train.origin if (tb.train) else "N/A"
            destination = tb.train.destination if (tb.train) else "N/A"
            stops, items = get_transit_stops_and_amenities(origin, destination, "train", train_name)
            stops_str = ", ".join([f"{s['name']} (stop for {s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            lines.append(
                f"- Train Booking: {train_name} ({train_num}) from {origin} to {destination}. Travel Date: {tb.travel_date}. Passenger: {tb.passenger_name}, Seats: {tb.num_seats}. Status: {tb.status}. Fare: INR {tb.total_fare_inr}. Intermediate Stops: {stops_str}. Complimentary Inclusions: {items_str}."
            )
            
    # Bus Bookings
    bus_bookings = db.query(BusBooking).filter(BusBooking.user_id == user_id, BusBooking.status != "cancelled").order_by(BusBooking.id.desc()).limit(5).all()
    if bus_bookings:
        lines.append("User Bus Bookings:")
        for bb in bus_bookings:
            operator = bb.bus.operator_name if (bb.bus) else "Bus Operator"
            bus_type = bb.bus.bus_type if (bb.bus) else "AC"
            origin = bb.bus.origin if (bb.bus) else "N/A"
            destination = bb.bus.destination if (bb.bus) else "N/A"
            stops, items = get_transit_stops_and_amenities(origin, destination, "bus", operator)
            stops_str = ", ".join([f"{s['name']} (stop for {s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            lines.append(
                f"- Bus Booking: Bus with {operator} ({bus_type}) from {origin} to {destination}. Travel Date: {bb.travel_date}. Passenger: {bb.passenger_name}, Seats: {bb.num_seats}. Status: {bb.status}. Fare: INR {bb.total_fare_inr}. Intermediate Stops: {stops_str}. Complimentary Inclusions: {items_str}."
            )
            
    # Flight Bookings
    flight_bookings = db.query(FlightBooking).filter(FlightBooking.user_id == user_id, FlightBooking.status != "cancelled").order_by(FlightBooking.id.desc()).limit(5).all()
    if flight_bookings:
        lines.append("User Flight Bookings:")
        for fb in flight_bookings:
            airline = fb.flight.airline if (fb.flight) else "Airline"
            flight_num = fb.flight.flight_number if (fb.flight) else "N/A"
            origin = fb.flight.origin if (fb.flight) else "N/A"
            destination = fb.flight.destination if (fb.flight) else "N/A"
            stops, items = get_transit_stops_and_amenities(origin, destination, "flight", airline)
            stops_str = ", ".join([f"{s['name']} (stop for {s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            lines.append(
                f"- Flight Booking: {airline} ({flight_num}) from {origin} to {destination}. Travel Date: {fb.travel_date}. Passenger: {fb.passenger_name}, Seats: {fb.num_seats}. Status: {fb.status}. Fare: INR {fb.total_fare_inr}. Intermediate Stops: {stops_str}. Complimentary Inclusions: {items_str}."
            )
            
    # Transit Bookings (generic Booking model)
    transit_bookings = db.query(Booking).filter(Booking.user_id == user_id, Booking.status != "cancelled").order_by(Booking.id.desc()).limit(5).all()
    if transit_bookings:
        lines.append("User Transit Bookings:")
        for b in transit_bookings:
            opt = get_transport_option_by_id(b.transport_option_id, db)
            mode = "Transit"
            operator = "Unknown"
            origin = "N/A"
            destination = "N/A"
            stops_str = "Direct (no stops)"
            items_str = "Standard amenities"
            if opt:
                mode = opt.mode
                operator = opt.operator
                origin = opt.origin
                destination = opt.destination
                stops, items = get_transit_stops_and_amenities(opt.origin, opt.destination, opt.mode, opt.operator)
                stops_str = ", ".join([f"{s['name']} (stop for {s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
                items_str = ", ".join(items) if items else "Standard amenities"
            else:
                try:
                    mode = b.transport_option_id.split("_")[0]
                except Exception:
                    pass
            lines.append(
                f"- Transit Booking: {mode.capitalize()} with {operator} from {origin} to {destination}. Travel Date: {b.travel_date}. Passenger: {b.passenger_name}, Fare: INR {b.total_fare_inr}. Status: {b.status}. Intermediate Stops: {stops_str}. Complimentary Inclusions: {items_str}."
            )

    # Cab Bookings (ProviderBooking)
    cab_bookings = db.query(ProviderBooking).filter(ProviderBooking.user_id == user_id, ProviderBooking.status != "cancelled").order_by(ProviderBooking.id.desc()).limit(5).all()
    if cab_bookings:
        lines.append("User Cab Bookings:")
        for cb in cab_bookings:
            v_name = cb.vehicle.vehicle_name if (cb.vehicle) else "Cab"
            provider_name = cb.vehicle.provider.company_name if (cb.vehicle and cb.vehicle.provider) else "Cab Provider"
            p_loc = cb.pickup_location or "N/A"
            d_loc = cb.dropoff_location or "N/A"
            p_name = p_loc.split("|||")[0] if "|||" in p_loc else p_loc
            d_name = d_loc.split("|||")[0] if "|||" in d_loc else d_loc
            stops, items = get_transit_stops_and_amenities(p_name, d_name, "cab", v_name)
            stops_str = ", ".join([f"{s['name']} (stop for {s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            lines.append(
                f"- Cab Booking: {v_name} with {provider_name} from {p_name} to {d_name}. Travel Date: {cb.travel_date}. Passenger: {cb.passenger_name}, Seats: {cb.num_seats}. Status: {cb.status}. Fare: INR {cb.total_fare_inr}. Intermediate Stops: {stops_str}. Complimentary Inclusions: {items_str}."
            )

    return "\n".join(lines)


class ChatMessage(BaseModel):
    message: str
    history: Optional[list[dict]] = []


@router.post("/chat")
async def trip_chat(
    request: Request,
    body: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    AI-powered conversational trip planning chatbot.
    Supports multi-turn conversation with history.
    """
    try:
        user_context = None
        opt_user = get_optional_user(request)
        
        if opt_user:
            user_context = build_user_context(int(opt_user["user_id"]), db)
            
        result = await chat_with_roadbuddy(
            message=body.message,
            history=body.history,
            user_context=user_context,
            db=db,
            user_id=int(opt_user["user_id"]) if opt_user else None,
        )
        return result
    except RuntimeError as e:
        print(f"[CHAT DEBUG] Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
class SafetyCheckRequest(BaseModel):
    origin: str
    destination: str
    travel_date: str
    departure_time: Optional[str] = "08:00"
    vehicle_type: Optional[str] = "car"
    num_people: Optional[int] = 2


@router.post("/safety-check")
async def check_route_safety(request: SafetyCheckRequest):
    """
    AI-powered route safety analyzer.
    Flags dangerous stretches, seasonal hazards and gives safety score.
    """
    try:
        result = await analyze_route_safety(
            origin=request.origin,
            destination=request.destination,
            travel_date=request.travel_date,
            departure_time=request.departure_time,
            vehicle_type=request.vehicle_type,
            num_people=request.num_people,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
class RecommendationRequest(BaseModel):
    home_city: str
    budget_inr: float
    group_type: Optional[str] = "friends"
    num_people: Optional[int] = 2
    duration_days: Optional[int] = 3
    season: Optional[str] = "winter"
    interests: Optional[list[str]] = ["sightseeing"]


@router.post("/recommendations")
async def trip_recommendations(request: RecommendationRequest):
    """
    AI-powered personalized trip recommendations.
    Suggests 5 trips based on budget, group type, season and interests.
    """
    try:
        result = await get_trip_recommendations(
            home_city=request.home_city,
            budget_inr=request.budget_inr,
            group_type=request.group_type,
            num_people=request.num_people,
            duration_days=request.duration_days,
            season=request.season,
            interests=request.interests,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trip_id}/end")
def end_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a trip and all its associated bookings as completed.
    """
    user_id = int(current_user["user_id"])
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized access")

    # 1. Update trip status
    trip.status = "completed"

    # 2. Find and update travel bookings associated with this trip's start_date / route
    from app.models.models import Booking, ProviderBooking, FoodOrder, Journal, HotelBooking

    # Update general transit bookings (bus, train, flight) on the trip date to completed
    transit_bookings = db.query(Booking).filter(
        Booking.user_id == user_id,
        Booking.travel_date == trip.start_date,
        Booking.status == "confirmed"
    ).all()
    for b in transit_bookings:
        b.status = "completed"

    # Update hotel bookings checking in on this trip date to completed
    hotel_bookings = db.query(HotelBooking).filter(
        HotelBooking.user_id == user_id,
        HotelBooking.check_in_date == trip.start_date,
        HotelBooking.status == "confirmed"
    ).all()
    for hb in hotel_bookings:
        hb.status = "completed"

    # Update cab provider bookings on the trip date to completed
    cab_bookings = db.query(ProviderBooking).filter(
        ProviderBooking.user_id == user_id,
        ProviderBooking.travel_date == trip.start_date,
        ProviderBooking.status == "confirmed"
    ).all()
    for cb in cab_bookings:
        cb.status = "completed"

    # Update food orders to completed
    food_orders = db.query(FoodOrder).filter(
        FoodOrder.user_id == user_id,
        FoodOrder.status == "confirmed"
    ).all()
    for order in food_orders:
        order.status = "completed"

    # 3. Create or update a Journal summary for the trip
    journal = db.query(Journal).filter(Journal.trip_id == str(trip_id)).first()
    if not journal:
        journal = Journal(
            trip_id=str(trip_id),
            user_id=user_id,
            total_expense_inr=0.0
        )
        db.add(journal)
        db.commit()
        db.refresh(journal)

    # Compile total expenses from all travel bookings and food orders
    total_hotel_cost = sum(hb.total_price_inr for hb in hotel_bookings)
    total_transit_cost = sum(b.total_fare_inr for b in transit_bookings)
    total_cab_cost = sum(cb.total_fare_inr for cb in cab_bookings)
    total_food_cost = sum(order.total_price_inr for order in food_orders)

    # Save expenses directly into the trip record
    trip.hotel_cost_inr = total_hotel_cost
    trip.transport_fare_inr = total_transit_cost + total_cab_cost
    trip.food_cost_inr = total_food_cost
    
    trip.total_cost_inr = (trip.fuel_cost_inr or 0.0) + (trip.toll_cost_inr or 0.0) + trip.hotel_cost_inr + trip.transport_fare_inr + trip.food_cost_inr

    # Save total expenses to journal record
    if journal:
        journal.total_expense_inr = trip.total_cost_inr

    db.commit()

    # Recompute user travel preferences snapshot
    try:
        from app.services.preference_engine import compute_user_preferences
        compute_user_preferences(db, user_id)
    except Exception as pref_err:
        print(f"Failed to recompute preferences for user {user_id}: {pref_err}")

    return {"success": True, "message": "Trip and all associated bookings marked as completed."}


# ---------------- QUICK ITINERARY GENERATOR ----------------

FOREIGN_DESTINATION_KEYWORDS = {
    "paris", "london", "new york", "tokyo", "dubai", "singapore", "bali", "thailand",
    "bangkok", "switzerland", "italy", "france", "usa", "america", "uk", "united kingdom",
    "japan", "china", "germany", "spain", "australia", "canada", "los angeles", "chicago",
    "san francisco", "miami", "las vegas", "toronto", "vancouver", "sydney", "melbourne",
    "rome", "barcelona", "madrid", "amsterdam", "berlin", "munich", "vienna", "prague",
    "budapest", "istanbul", "cairo", "cape town", "rio de janeiro", "buenos aires",
    "mexico city", "seoul", "beijing", "shanghai", "hong kong", "taiwan", "kuala lumpur",
    "vietnam", "hanoi", "phuket", "maldives", "sri lanka", "colombo", "kathmandu", "nepal",
    "bhutan", "pakistan", "bangladesh", "dhaka", "afghanistan", "iran", "iraq", "saudi arabia",
    "qatar", "doha", "abu dhabi", "sharjah", "kuwait", "bahrain", "oman", "muscat", "russia",
    "moscow", "ukraine", "poland", "greece", "athens", "turkey", "egypt", "south africa",
    "brazil", "argentina", "new zealand", "auckland", "hawaii", "alaska", "sweden", "norway",
    "denmark", "finland", "portugal", "lisbon", "zurich", "geneva", "austria"
}

INDIAN_DESTINATION_KEYWORDS = {
    "manali", "goa", "jaipur", "kerala", "leh", "ladakh", "delhi", "mumbai", "bengaluru",
    "bangalore", "kolkata", "chennai", "hyderabad", "pune", "ahmedabad", "surat", "udaipur",
    "jodhpur", "shimla", "dharamshala", "risikesh", "rishikesh", "haridwar", "varanasi",
    "agra", "mussoorie", "nainital", "darjeeling", "gangtok", "shillong", "munnar",
    "wayanad", "alleppey", "kochi", "coorg", "ooty", "kodaikanal", "pondicherry",
    "puducherry", "andaman", "nicobar", "lakshadweep", "srinagar", "gulmarg", "pahalgam",
    "jammu", "kashmir", "amritsar", "vrindavan", "mathura", "ayodhya", "ujjain", "indore",
    "bhopal", "gwalior", "nashik", "shirdi", "lonavala", "khandala", "mahableshwar",
    "hampi", "gokarna", "mysore", "mysuru", "chikmagalur", "coimbatore", "madurai", "rameshwaram",
    "kanyakumari", "tirupati", "vizag", "visakhapatnam", "bhubaneswar", "puri", "cuttack",
    "guwahati", "kaziranga", "tawang", "imphal", "kohima", "aizawl", "agartala", "ranchi",
    "jamshedpur", "patna", "raipur", "dehradun", "rohtak", "chandigarh", "mohali", "panchkula",
    "noida", "gurugram", "gurgaon", "faridabad", "ghaziabad", "india"
}

async def is_destination_in_india(destination: str) -> bool:
    import re, httpx
    dest_cleaned = destination.strip().lower()

    # Fast match against known foreign keywords
    words = re.split(r'[\s,]+', dest_cleaned)
    for word in words:
        if word in FOREIGN_DESTINATION_KEYWORDS:
            return False

    # Fast match against known Indian cities / destinations
    for word in words:
        if word in INDIAN_DESTINATION_KEYWORDS:
            return True

    # Geocoding fallback check via OpenStreetMap / Nominatim
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            url = f"https://nominatim.openstreetmap.org/search?q={httpx.URL(dest_cleaned)}&format=json&addressdetails=1&limit=1"
            headers = {"User-Agent": "RoadBuddy-TravelApp/1.0"}
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    addr = data[0].get("address", {})
                    country_code = addr.get("country_code", "").lower()
                    country = addr.get("country", "").lower()
                    if country_code == "in" or "india" in country:
                        return True
                    else:
                        return False
    except Exception as e:
        print(f"Geocoding validation error for '{destination}': {e}")

    return True

class QuickItineraryRequest(BaseModel):
    destination: str
    days: int

@router.post("/quick-itinerary")
async def generate_quick_itinerary(
    data: QuickItineraryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate a quick day-by-day itinerary without times for a given destination and number of days."""
    destination = data.destination.strip()
    days = data.days

    if not destination:
        raise HTTPException(status_code=400, detail="Destination cannot be empty")
    if days < 1 or days > 14:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 14")

    # Enforce India-Only destinations
    if not await is_destination_in_india(destination):
        raise HTTPException(
            status_code=400,
            detail="🇮🇳 RoadBuddy Quick Itinerary is currently available only for destinations within India. Please enter a city or location inside India (e.g. Manali, Goa, Jaipur, Kerala, Leh)."
        )

    prompt = f"""You are RoadBuddy AI, an expert travel planner for India. Generate the ultimate high-quality, impressive day-by-day travel itinerary for a trip to {destination} in India for exactly {days} days.

CRITICAL INSTRUCTIONS:
1. Ensure all tourist spots, dhabas, cafes, and activities are strictly located in or near {destination}, India.
2. Group nearby tourist places, activities, and dining spots logically for each day to minimize travel time.
3. For each day, provide:
   - A list of best tourist attractions/activities to visit.
   - Recommended places to eat.
   - A descriptive, engaging summary paragraph of the day's theme/plan.
4. DO NOT include specific timestamps or time slots (no "Morning", "Afternoon", "09:00 AM", etc.). Just structure it as:
   - Day X:
     - Attractions: [List of places/activities]
     - Dining: [Recommended food/eateries]
     - Summary: [A rich, 3-4 sentence paragraph describing the flow of the day]
5. Make sure the destinations, spots, and dhabas/restaurants are real and located in or near {destination}.
6. Return ONLY a valid JSON object matching this structure:
{{
  "destination": "{destination}",
  "days_count": {days},
  "title": "A catchy title for the trip, e.g. Magical Goa Getaway",
  "itinerary": [
    {{
      "day": 1,
      "attractions": ["Place 1", "Place 2", "Activity 3"],
      "dining": ["Restaurant/Cafe A", "Local food recommendation B"],
      "summary": "Start your trip by exploring the historic charm of..."
    }}
  ]
}}
Do not include any explanation, markdown formatting (no ```json, no ```), or notes. Return raw JSON only.
"""

    from app.services.groq_client import call_groq
    from app.core.config import settings

    try:
        if settings.gemini_api_key or settings.groq_api_key:
            try:
                result = await call_groq(prompt)
                return result
            except Exception as api_err:
                print(f"Quick itinerary generation API call failed ({api_err}). Falling back to mock itinerary.")

        # Fallback mock itinerary if API call failed or no API keys are set
        itinerary = []
        for day in range(1, days + 1):
            itinerary.append({
                "day": day,
                "attractions": [f"Famous Landmark {day}A", f"Scenic Viewpoint {day}B", f"Cultural Activity {day}C"],
                "dining": [f"Popular Local Cafe {day}", f"Traditional Dinner spot {day}"],
                "summary": f"Discover the wonderful sights of {destination} on Day {day}. Start with a visit to the local landmark followed by a scenic walk. Enjoy authentic cuisine for lunch and wrap up the evening exploring markets."
            })
        return {
            "destination": destination,
            "days_count": days,
            "title": f"Explore the Best of {destination}",
            "itinerary": itinerary
        }
    except Exception as e:
        print(f"Quick itinerary generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate itinerary. Please try again.")