from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey,Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base



# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, server_default=func.now())

    vehicles   = relationship("Vehicle", back_populates="owner")
    trips      = relationship("Trip",    back_populates="user")
    preference = relationship("UserPreference", back_populates="user", uselist=False)


# ── User Preferences ──────────────────────────────────────────────────────────

class UserPreference(Base):
    __tablename__ = "user_preferences"

    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    preferred_budget_tier   = Column(String, nullable=True)     # "budget" / "mid" / "luxury"
    avoid_tolls_default     = Column(Boolean, default=False)
    avoid_highways_default  = Column(Boolean, default=False)
    preferred_accommodation = Column(String, nullable=True)     # "hotel" / "homestay" / "budget-stay"
    preferred_travel_mode   = Column(String, nullable=True)     # "own_vehicle" / "cab_service" / "bus" / "train" / "flight"
    last_computed_at        = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="preference")



# ── Vehicles ──────────────────────────────────────────────────────────────────

class Vehicle(Base):
    __tablename__ = "vehicles"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    name         = Column(String, nullable=False)
    fuel_type    = Column(String, nullable=False)
    category     = Column(String, nullable=False)
    mileage_kmpl = Column(Float, nullable=False)

    owner = relationship("User",  back_populates="vehicles")
    trips = relationship("Trip",  back_populates="vehicle")


# ── Trips ─────────────────────────────────────────────────────────────────────

class Trip(Base):
    __tablename__ = "trips"

    id                 = Column(Integer, primary_key=True, index=True)
    user_id            = Column(Integer, ForeignKey("users.id"),    nullable=False)
    vehicle_id         = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    origin             = Column(String, nullable=False)
    destination        = Column(String, nullable=False)
    origin_lat         = Column(Float, nullable=True)
    origin_lon         = Column(Float, nullable=True)
    destination_lat    = Column(Float, nullable=True)
    destination_lon    = Column(Float, nullable=True)
    start_date         = Column(String, nullable=False)
    end_date           = Column(String, nullable=True)
    budget_inr         = Column(Float,  nullable=False)
    travel_mode        = Column(String, nullable=False)
    group_type         = Column(String, nullable=True)
    num_people         = Column(Integer, default=1)
    fuel_cost_inr      = Column(Float, default=0)
    toll_cost_inr      = Column(Float, default=0)
    transport_fare_inr = Column(Float, default=0)
    return_fare_inr    = Column(Float, default=0)
    hotel_cost_inr     = Column(Float, default=0)
    food_cost_inr      = Column(Float, default=0)
    total_cost_inr     = Column(Float, default=0)
    ai_summary         = Column(String, nullable=True)
    status             = Column(String, default="active")
    created_at         = Column(DateTime, server_default=func.now())

    user    = relationship("User",    back_populates="trips")
    vehicle = relationship("Vehicle", back_populates="trips")
    stops   = relationship("TripStop", back_populates="trip")


# ── Trip Stops ────────────────────────────────────────────────────────────────

class TripStop(Base):
    __tablename__ = "trip_stops"

    id         = Column(Integer, primary_key=True, index=True)
    trip_id    = Column(Integer, ForeignKey("trips.id"), nullable=False)
    day        = Column(Integer, nullable=False)
    time_slot  = Column(String,  nullable=False)
    place_name = Column(String,  nullable=False)
    place_type = Column(String,  nullable=False)
    description       = Column(String, nullable=True)
    estimated_cost_inr = Column(Float, nullable=True)

    trip = relationship("Trip", back_populates="stops")


# ── Transport Options ─────────────────────────────────────────────────────────

class TransportOption(Base):
    __tablename__ = "transport_options"

    id              = Column(Integer, primary_key=True, index=True)
    origin          = Column(String, nullable=False)
    destination     = Column(String, nullable=False)
    mode            = Column(String, nullable=False)
    operator        = Column(String, nullable=False)
    departure_time  = Column(String, nullable=False)
    arrival_time    = Column(String, nullable=False)
    duration_hrs    = Column(Float,  nullable=False)
    fare_inr        = Column(Float,  nullable=False)
    seats_available = Column(Integer, nullable=False)


# ── Bookings ──────────────────────────────────────────────────────────────────

class Booking(Base):
    __tablename__ = "bookings"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False)
    transport_option_id = Column(String,  nullable=False)
    passenger_name      = Column(String,  nullable=False)
    travel_date         = Column(String,  nullable=False)
    include_return      = Column(Boolean, default=False)
    return_date         = Column(String,  nullable=True)
    going_fare_inr      = Column(Float,   nullable=False)
    return_fare_inr     = Column(Float,   default=0)
    total_fare_inr      = Column(Float,   nullable=False)
    status              = Column(String,  default="confirmed")
    selected_seats      = Column(String,  nullable=True)
    travel_class        = Column(String,  nullable=True)
    duffel_order_id     = Column(String,  nullable=True)
    created_at          = Column(DateTime, server_default=func.now())

    user = relationship("User")

# ── Community Routes ──────────────────────────────────────────────────────────

class CommunityRoute(Base):
    __tablename__ = "community_routes"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    trip_id     = Column(String,  nullable=False)
    title       = Column(String,  nullable=False)
    description = Column(String,  nullable=False)
    tags        = Column(String,  nullable=True)   # stored as comma separated
    is_public   = Column(Boolean, default=True)
    origin      = Column(String,  default="Unknown")
    destination = Column(String,  default="Unknown")
    avg_rating  = Column(Float,   default=0.0)
    total_reviews = Column(Integer, default=0)
    clone_count = Column(Integer, default=0)
    created_at  = Column(DateTime, server_default=func.now())

    user    = relationship("User")
    reviews = relationship("RouteReview", back_populates="route")


# ── Route Reviews ─────────────────────────────────────────────────────────────

class RouteReview(Base):
    __tablename__ = "route_reviews"

    id          = Column(Integer, primary_key=True, index=True)
    route_id    = Column(Integer, ForeignKey("community_routes.id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating      = Column(Integer, nullable=False)
    review_text = Column(String,  nullable=False)
    tags        = Column(String,  nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    route = relationship("CommunityRoute", back_populates="reviews")
    user  = relationship("User")

# ── Journal ───────────────────────────────────────────────────────────────────

class Journal(Base):
    __tablename__ = "journals"

    id                = Column(Integer, primary_key=True, index=True)
    trip_id           = Column(String,  nullable=False, unique=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_expense_inr = Column(Float,   default=0.0)
    is_public         = Column(Boolean, default=False)
    created_at        = Column(DateTime, server_default=func.now())

    user    = relationship("User")
    entries = relationship("JournalEntry", back_populates="journal")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id         = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=False)
    stop_name  = Column(String,  nullable=False)
    notes      = Column(String,  nullable=True)
    expense_inr = Column(Float,  default=0.0)
    lat        = Column(Float,   nullable=True)
    lng        = Column(Float,   nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    journal = relationship("Journal", back_populates="entries")
    
# ── Hotels ─────────────────────────────────────────────────────────────────
 
class Hotel(Base):
    __tablename__ = "hotels"
 
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    city          = Column(String, nullable=False, index=True)
    address       = Column(String, nullable=True)
    star_rating   = Column(Float, default=3.0)
    price_per_night_inr = Column(Float, nullable=False)
    total_rooms   = Column(Integer, default=10)
    rooms_booked  = Column(Integer, default=0)
    amenities     = Column(String, nullable=True)   # comma separated
    image_url     = Column(String, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
 
    avg_rating    = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)

    bookings = relationship("HotelBooking", back_populates="hotel")
    reviews  = relationship("HotelReview", back_populates="hotel", cascade="all, delete-orphan")

    @property
    def rooms_available(self):
        return max(self.total_rooms - self.rooms_booked, 0)
 
 
class HotelBooking(Base):
    __tablename__ = "hotel_bookings"
 
    id            = Column(Integer, primary_key=True, index=True)
    hotel_id      = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    check_in_date = Column(String, nullable=False)
    check_out_date= Column(String, nullable=False)
    num_rooms     = Column(Integer, default=1)
    num_guests    = Column(Integer, default=1)
    total_price_inr = Column(Float, nullable=False)
    status        = Column(String, default="confirmed")
    duffel_booking_id = Column(String, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
 
    hotel = relationship("Hotel", back_populates="bookings")
    user  = relationship("User")


class HotelReview(Base):
    __tablename__ = "hotel_reviews"

    id          = Column(Integer, primary_key=True, index=True)
    hotel_id    = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating      = Column(Integer, nullable=False)
    review_text = Column(String, nullable=False)
    created_at  = Column(DateTime, server_default=func.now())

    hotel = relationship("Hotel", back_populates="reviews")
    user  = relationship("User")
 
 
# ── Trains ─────────────────────────────────────────────────────────────────
 
class Train(Base):
    __tablename__ = "trains"
 
    id              = Column(Integer, primary_key=True, index=True)
    train_name      = Column(String, nullable=False)
    train_number    = Column(String, nullable=False)
    origin          = Column(String, nullable=False, index=True)
    destination     = Column(String, nullable=False, index=True)
    departure_time  = Column(String, nullable=False)
    arrival_time    = Column(String, nullable=False)
    duration_hrs    = Column(Float, nullable=False)
    fare_inr        = Column(Float, nullable=False)
    total_seats     = Column(Integer, default=100)
    seats_booked    = Column(Integer, default=0)
    travel_class    = Column(String, default="Sleeper")  # Sleeper, AC3, AC2, AC1
    created_at      = Column(DateTime, server_default=func.now())
 
    bookings = relationship("TrainBooking", back_populates="train")
 
    @property
    def seats_available(self):
        return max(self.total_seats - self.seats_booked, 0)
 
 
class TrainBooking(Base):
    __tablename__ = "train_bookings"
 
    id              = Column(Integer, primary_key=True, index=True)
    train_id        = Column(Integer, ForeignKey("trains.id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_name  = Column(String, nullable=False)
    travel_date     = Column(String, nullable=False)
    num_seats       = Column(Integer, default=1)
    total_fare_inr  = Column(Float, nullable=False)
    status          = Column(String, default="confirmed")
    created_at      = Column(DateTime, server_default=func.now())
 
    train = relationship("Train", back_populates="bookings")
    user  = relationship("User")
 
 
# ── Buses ──────────────────────────────────────────────────────────────────
 
class Bus(Base):
    __tablename__ = "buses"
 
    id              = Column(Integer, primary_key=True, index=True)
    operator_name   = Column(String, nullable=False)
    bus_type        = Column(String, default="AC Sleeper")  # AC Seater, AC Sleeper, Non-AC
    origin          = Column(String, nullable=False, index=True)
    destination     = Column(String, nullable=False, index=True)
    departure_time  = Column(String, nullable=False)
    arrival_time    = Column(String, nullable=False)
    duration_hrs    = Column(Float, nullable=False)
    fare_inr        = Column(Float, nullable=False)
    total_seats     = Column(Integer, default=40)
    seats_booked    = Column(Integer, default=0)
    created_at      = Column(DateTime, server_default=func.now())
 
    bookings = relationship("BusBooking", back_populates="bus")
 
    @property
    def seats_available(self):
        return max(self.total_seats - self.seats_booked, 0)
 
 
class BusBooking(Base):
    __tablename__ = "bus_bookings"
 
    id              = Column(Integer, primary_key=True, index=True)
    bus_id          = Column(Integer, ForeignKey("buses.id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_name  = Column(String, nullable=False)
    travel_date     = Column(String, nullable=False)
    num_seats       = Column(Integer, default=1)
    total_fare_inr  = Column(Float, nullable=False)
    status          = Column(String, default="confirmed")
    created_at      = Column(DateTime, server_default=func.now())
 
    bus  = relationship("Bus", back_populates="bookings")
    user = relationship("User")
 
 
# ── Flights ────────────────────────────────────────────────────────────────
 
class Flight(Base):
    __tablename__ = "flights"
 
    id              = Column(Integer, primary_key=True, index=True)
    airline         = Column(String, nullable=False)
    flight_number   = Column(String, nullable=False)
    origin          = Column(String, nullable=False, index=True)
    destination     = Column(String, nullable=False, index=True)
    departure_time  = Column(String, nullable=False)
    arrival_time    = Column(String, nullable=False)
    duration_hrs    = Column(Float, nullable=False)
    fare_inr        = Column(Float, nullable=False)
    total_seats     = Column(Integer, default=180)
    seats_booked    = Column(Integer, default=0)
    travel_class    = Column(String, default="Economy")
    created_at      = Column(DateTime, server_default=func.now())
 
    bookings = relationship("FlightBooking", back_populates="flight")
 
    @property
    def seats_available(self):
        return max(self.total_seats - self.seats_booked, 0)
 
 
class FlightBooking(Base):
    __tablename__ = "flight_bookings"
 
    id              = Column(Integer, primary_key=True, index=True)
    flight_id       = Column(Integer, ForeignKey("flights.id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_name  = Column(String, nullable=False)
    travel_date     = Column(String, nullable=False)
    num_seats       = Column(Integer, default=1)
    total_fare_inr  = Column(Float, nullable=False)
    status          = Column(String, default="confirmed")
    created_at      = Column(DateTime, server_default=func.now())
 
    flight = relationship("Flight", back_populates="bookings")
    user   = relationship("User")
 
 
# ── Travel Service Providers ──────────────────────────────────────────────
 
class Provider(Base):
    __tablename__ = "providers"

    id              = Column(Integer, primary_key=True, index=True)
    company_name    = Column(String, nullable=True)
    contact_person  = Column(String, nullable=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    password_hash   = Column(String, nullable=False)
    phone           = Column(String, nullable=True)
    city            = Column(String, nullable=True)
    service_type    = Column(String, nullable=True)
    is_verified     = Column(Boolean, default=False)
    created_at      = Column(DateTime, server_default=func.now())
    alternate_email = Column(String, nullable=True)
    booking_mode    = Column(String, nullable=True)

    vehicles       = relationship("ProviderVehicle", back_populates="provider")
    vehicle_assets = relationship("ProviderVehicleAsset", back_populates="provider")


class ProviderVehicleAsset(Base):
    __tablename__ = "provider_vehicle_assets"

    id              = Column(Integer, primary_key=True, index=True)
    provider_id     = Column(Integer, ForeignKey("providers.id"), nullable=False)
    vehicle_type    = Column(String, nullable=False)   # sedan, suv, hatchback, mini_bus, traveller_bus, luxury_bus
    vehicle_name    = Column(String, nullable=False)   # e.g. "Volvo Multi-Axle", "Tempo Traveller"
    driver_included = Column(Boolean, default=True)
    total_seats     = Column(Integer, default=40)
    created_at      = Column(DateTime, server_default=func.now())

    provider = relationship("Provider", back_populates="vehicle_assets")


class ProviderVehicle(Base):
    __tablename__ = "provider_vehicles"
 
    id              = Column(Integer, primary_key=True, index=True)
    provider_id     = Column(Integer, ForeignKey("providers.id"), nullable=False)
    vehicle_asset_id = Column(Integer, ForeignKey("provider_vehicle_assets.id"), nullable=True)
    vehicle_type    = Column(String, nullable=False)   # sedan, suv, hatchback, mini_bus, traveller_bus
    vehicle_name    = Column(String, nullable=False)   # e.g. "Swift Dzire", "Tempo Traveller 12-seater"
    driver_included = Column(Boolean, default=True)
    origin          = Column(String, nullable=False, index=True)
    destination     = Column(String, nullable=False, index=True)
    departure_time  = Column(String, nullable=True)
    arrival_time    = Column(String, nullable=True)
    price_per_km_inr = Column(Float, nullable=True)
    fixed_fare_inr  = Column(Float, nullable=True)
    total_seats     = Column(Integer, default=4)
    seats_booked    = Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)
    pickup_points   = Column(String, nullable=True)
    dropoff_points  = Column(String, nullable=True)
    service_dates   = Column(String, nullable=True)
    avg_rating      = Column(Float, default=0.0)
    total_reviews   = Column(Integer, default=0)
    created_at      = Column(DateTime, server_default=func.now())
 
    provider = relationship("Provider", back_populates="vehicles")
    bookings = relationship("ProviderBooking", back_populates="vehicle")
    vehicle_asset = relationship("ProviderVehicleAsset")
    reviews  = relationship("VehicleReview", back_populates="vehicle", cascade="all, delete-orphan")
 
    @property
    def seats_booked_today(self):
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if session is None:
            return self.seats_booked
        
        from datetime import date
        today_str = date.today().isoformat()
        
        from app.models.models import ProviderBooking
        bookings = session.query(ProviderBooking).filter(
            ProviderBooking.vehicle_id == self.id,
            ProviderBooking.travel_date == today_str,
            ProviderBooking.status != "cancelled"
        ).all()
        
        if self.destination == "Private":
            return self.total_seats if bookings else 0
        else:
            return sum(b.num_seats for b in bookings)

    @property
    def seats_available(self):
        return max(self.total_seats - self.seats_booked_today, 0)
 
 
class ProviderBooking(Base):
    __tablename__ = "provider_bookings"
 
    id              = Column(Integer, primary_key=True, index=True)
    vehicle_id      = Column(Integer, ForeignKey("provider_vehicles.id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_name  = Column(String, nullable=False)
    passenger_phone = Column(String, nullable=True)
    passenger_email = Column(String, nullable=True)
    travel_date     = Column(String, nullable=False)
    num_seats       = Column(Integer, default=1)
    pickup_location = Column(String, nullable=True)
    dropoff_location = Column(String, nullable=True)
    selected_seats  = Column(String, nullable=True)
    total_fare_inr  = Column(Float, nullable=False)
    status          = Column(String, default="confirmed")
    navigation_status = Column(String, nullable=True)
    driver_lat      = Column(Float, nullable=True)
    driver_lon      = Column(Float, nullable=True)
    passenger_details = Column(String, nullable=True)
    message_unread  = Column(Boolean, default=False)
    provider_unread = Column(Boolean, default=True)
    created_at      = Column(DateTime, server_default=func.now())
 
    vehicle = relationship("ProviderVehicle", back_populates="bookings")
    user    = relationship("User")
 
    @property
    def vehicle_name(self):
        return self.vehicle.vehicle_name if self.vehicle else "Vehicle"
 
    @property
    def passenger_details_parsed(self):
        if self.passenger_details:
            import json
            try:
                return json.loads(self.passenger_details)
            except Exception:
                pass
        return []


# ── Food & Restaurants ────────────────────────────────────────────────────────

class Restaurant(Base):
    __tablename__ = "restaurants"

    id              = Column(Integer, primary_key=True, index=True)
    provider_id     = Column(Integer, ForeignKey("providers.id"), nullable=True)
    name            = Column(String, nullable=False)
    city            = Column(String, nullable=False, index=True)
    address         = Column(String, nullable=False)
    rating          = Column(Float, default=4.0)
    reviews_count   = Column(Integer, default=0)
    latitude        = Column(Float, nullable=True)
    longitude       = Column(Float, nullable=True)
    contact_number  = Column(String, nullable=True)
    image_url       = Column(String, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    menu_items = relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")
    orders = relationship("FoodOrder", back_populates="restaurant", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id              = Column(Integer, primary_key=True, index=True)
    restaurant_id   = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name            = Column(String, nullable=False)
    description     = Column(String, nullable=True)
    price_inr       = Column(Float, nullable=False)
    category        = Column(String, default="Veg")  # Veg, Non-Veg, Egg, Beverage, Dessert
    rating          = Column(Float, default=4.0)
    created_at      = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="menu_items")
    reviews = relationship("FoodReview", back_populates="menu_item", cascade="all, delete-orphan")


class FoodOrder(Base):
    __tablename__ = "food_orders"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    restaurant_id   = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    items_json      = Column(String, nullable=False)  # JSON list of {menu_item_id, name, quantity, price}
    total_amount    = Column(Float, nullable=False)
    status          = Column(String, default="paid")  # paid, preparing, ready, completed
    preparation_time_mins = Column(Integer, default=20)  # Provider set time
    user_arrival_time_mins = Column(Integer, default=30)  # User arrival offset in minutes
    payment_method   = Column(String, default="prepaid")  # prepaid (wallet/card)
    created_at      = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="orders")
    user = relationship("User")


class FoodReview(Base):
    __tablename__ = "food_reviews"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    menu_item_id    = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    rating          = Column(Integer, default=5)  # 1 to 5 stars
    comment         = Column(String, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    menu_item = relationship("MenuItem", back_populates="reviews")
    user = relationship("User")


class VehicleReview(Base):
    __tablename__ = "vehicle_reviews"

    id          = Column(Integer, primary_key=True, index=True)
    vehicle_id  = Column(Integer, ForeignKey("provider_vehicles.id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating      = Column(Integer, nullable=False)
    review_text = Column(String, nullable=False)
    created_at  = Column(DateTime, server_default=func.now())

    vehicle = relationship("ProviderVehicle", back_populates="reviews")
    user    = relationship("User")


# ── Fuel Station Availability Feature ─────────────────────────────────────────
# NOTE: These models are new and separate from the Provider/Vehicle models above.
# FuelStationOperator is a pump-owner concept; Provider is a cab/vehicle-service concept.

class FuelStation(Base):
    """
    A petrol/diesel/CNG/EV station along a highway route.
    is_demo=True marks synthetic/test stations used for demo purposes — never mix
    with real production data that has is_demo=False.
    """
    __tablename__ = "fuel_stations"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    brand       = Column(String, nullable=True)          # e.g. IOCL, BPCL, HPCL, private
    latitude    = Column(Float, nullable=False)
    longitude   = Column(Float, nullable=False)
    address     = Column(String, nullable=True)
    route_tag   = Column(String, nullable=True, index=True)  # e.g. "NH48-Jaipur-Delhi"
    is_demo     = Column(Boolean, default=False, nullable=False)
    gstin       = Column(String, nullable=True)
    location_verified = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())

    fuel_types        = relationship("StationFuelType",    back_populates="station", cascade="all, delete-orphan")
    availability_log  = relationship("AvailabilityUpdate", back_populates="station", cascade="all, delete-orphan")
    operator          = relationship("FuelStationOperator", back_populates="station", uselist=False, cascade="all, delete-orphan")
    service_road_info = relationship("ServiceRoadInfo",    back_populates="station", uselist=False, cascade="all, delete-orphan")
    ev_charger_status = relationship("EVChargerStatus",    back_populates="station", uselist=False, cascade="all, delete-orphan")


class StationFuelType(Base):
    """
    Which fuel types a station offers.
    fuel_type: one of petrol | diesel | cng | ev
    """
    __tablename__ = "station_fuel_types"

    id          = Column(Integer, primary_key=True, index=True)
    station_id  = Column(Integer, ForeignKey("fuel_stations.id"), nullable=False)
    fuel_type   = Column(String, nullable=False)    # petrol | diesel | cng | ev
    is_offered  = Column(Boolean, default=True)

    station = relationship("FuelStation", back_populates="fuel_types")


class AvailabilityUpdate(Base):
    """
    Append-only log of availability reports per station+fuel_type.
    Always INSERT new rows; never UPDATE existing rows.
    This lets us recompute confidence from history at any point in time.

    source: operator | crowdsource
    reported_status: available | unavailable
    """
    __tablename__ = "availability_updates"

    id              = Column(Integer, primary_key=True, index=True)
    station_id      = Column(Integer, ForeignKey("fuel_stations.id"), nullable=False)
    fuel_type       = Column(String, nullable=False)     # petrol | diesel | cng | ev
    source          = Column(String, nullable=False)     # operator | crowdsource
    reported_status = Column(String, nullable=False)     # available | unavailable
    reported_at     = Column(DateTime, nullable=False, server_default=func.now())
    reported_by     = Column(Integer, nullable=True)     # operator_id or user_id; nullable for anonymous
    ttl_hours       = Column(Float, nullable=True)       # estimated time for how long fuel is 100% available

    station = relationship("FuelStation", back_populates="availability_log")


class FuelStationOperator(Base):
    """
    Owner/operator of a fuel station — completely separate from the Provider model
    which handles cab/vehicle services.

    verification_status:
        pending  — submitted but not yet verified (real future flow)
        verified — KYC confirmed (real future flow)
        demo     — synthetic/test operator for mentor demo; clearly distinguishable from real data

    kyc_document_reference is nullable/stub for now.
    # TODO (real implementation): integrate a KYC document verification service here.
    """
    __tablename__ = "fuel_station_operators"

    id                      = Column(Integer, primary_key=True, index=True)
    station_id              = Column(Integer, ForeignKey("fuel_stations.id"), nullable=True, unique=True)
    name                    = Column(String, nullable=True)
    phone_number            = Column(String, nullable=True)
    email                   = Column(String, nullable=True, unique=True)
    license_number          = Column(String, nullable=True)
    relationship_to_pump    = Column(String, nullable=True)  # owner | authorized_manager | dealer
    gov_id                  = Column(String, nullable=True)  # Aadhaar or PAN
    dealership_agreement_number = Column(String, nullable=True)
    kyc_document_reference  = Column(String, nullable=True)   # stub field; no real document stored yet
    verification_status     = Column(String, default="pending", nullable=False)  # pending | verified | demo
    api_key                 = Column(String, nullable=True, unique=True)  # stub operator auth token
    created_at              = Column(DateTime, server_default=func.now())

    station = relationship("FuelStation", back_populates="operator")


class ServiceRoadInfo(Base):
    """
    Service-road metadata for highway stations.
    Drivers often miss pump entries on service roads — this data lets a frontend
    trigger advance distance-based alerts (e.g. at 2km / 1km / 500m from entry).

    highway_side: left | right (relative to travel direction)
    entry_position: before_pump | after_pump
    """
    __tablename__ = "service_road_info"

    id                   = Column(Integer, primary_key=True, index=True)
    station_id           = Column(Integer, ForeignKey("fuel_stations.id"), nullable=False, unique=True)
    highway_side         = Column(String, nullable=True)    # left | right
    entry_position       = Column(String, nullable=True)    # before_pump | after_pump
    requires_u_turn      = Column(Boolean, default=False)
    entry_point_latitude  = Column(Float, nullable=True)
    entry_point_longitude = Column(Float, nullable=True)
    notes                = Column(Text, nullable=True)      # free text, e.g. "Entry visible from Delhi-bound side only"

    station = relationship("FuelStation", back_populates="service_road_info")


class EVChargerStatus(Base):
    """
    EV charger availability snapshot — separate from the confidence/decay model
    used for liquid fuels, because EV availability is about charger occupancy,
    not fuel stock confidence.
    """
    __tablename__ = "ev_charger_status"

    id                  = Column(Integer, primary_key=True, index=True)
    station_id          = Column(Integer, ForeignKey("fuel_stations.id"), nullable=False, unique=True)
    total_chargers      = Column(Integer, default=0)
    chargers_available  = Column(Integer, default=0)
    chargers_working    = Column(Integer, default=0)
    last_updated_at     = Column(DateTime, nullable=True)

    station = relationship("FuelStation", back_populates="ev_charger_status")