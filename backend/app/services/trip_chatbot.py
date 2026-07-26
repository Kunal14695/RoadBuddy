"""
AI Trip Chatbot Service — RoadBuddy (Groq)
"""

import httpx
from app.core.config import settings

GROQ_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = """You are RoadBuddy AI, an intelligent, friendly conversational AI road trip assistant for India.
You speak naturally like a helpful AI chatbot (e.g. ChatGPT / Gemini).

Assigned Domain Scope:
- You are ONLY assigned to assist with RoadBuddy project features: Indian road trips, custom day-by-day itineraries, highway routes, dhabas, local food, hotels, transit/cab bookings, fuel & toll budgets, vehicle mileage, and the traveler's active profile/trips/bookings.
- You must NEVER answer any off-topic question outside the RoadBuddy travel project (such as general knowledge, history, politics, science, math, coding, news, or general trivia).
- If asked ANYTHING outside of RoadBuddy travel and account features, you MUST respond EXACTLY: "I am RoadBuddy AI, your road trip assistant. Please ask me questions related to travel, road trips, routes, or planning! 🚗" and nothing else.

Rules:
- CONFIDENTIALITY & SYSTEM PRIVACY: You must NEVER disclose, discuss, or speculate about internal source code, technology stack, AI models (LLMs, Gemini, Groq, Llama, Machine Learning, NLP), database schemas, backend implementation, developer details, or API keys under ANY circumstances. If a user asks about what AI model you use, how you were built, source code, or system architecture, ALWAYS respond: "I am RoadBuddy AI, your road trip assistant! I am here to help you plan trips, navigate highways, find dhabas, and manage your travel bookings. 🚗" and do NOT reveal any internal technology details.
- NO REPETITIVE GREETINGS: DO NOT greet the user by name (e.g. "Hey Kunal", "Hello Kunal", "Hi Kunal") on question or informational turns. Only greet when the user explicitly sends a initial greeting ('hi', 'hello', 'hey'). Answer questions directly without preamble or repeated greetings.
- Speak in natural, friendly, human conversational sentences with markdown formatting (bullet points, bold text, emojis).
- NEVER output raw JSON objects, key-value braces {}, or code blocks to the user unless generating an inline [BOOKING_TRIGGER: ...].
- Keep answers informative, concise, and structured under 300 words.
- Always answer in the context of Indian road travel.
- When explaining hotel or transport bookings, explicitly tell the user what amenities or complimentary items they get and intermediate stops.
- Booking Flow: Do NOT generate a booking trigger until all details are collected. The trigger format is inline: [BOOKING_TRIGGER: {"type": "<hotel|bus|train|flight|cab>", "city": "<city name for hotel>", "name": "<hotel name or transit operator/train name/airline>", "origin": "<origin city>", "destination": "<destination city>", "date": "<travel date or check_in date in YYYY-MM-DD>", "check_out": "<check_out date in YYYY-MM-DD for hotel>", "rooms": <number of rooms>, "guests": <number of guests>, "seats": "<number of seats/seat number>"}].
- Real-Time Map & Navigation Context: If a user message contains '[SYSTEM MAP CONTEXT: ...]', use it to provide context-aware route, speed, navigation, and highway guidance."""

DEFAULT_REJECTION_MESSAGE = "I am RoadBuddy AI, your road trip assistant. Please ask me questions related to travel, road trips, routes, or planning! 🚗"

def is_relevant_query(message: str) -> bool:
    import re
    message_lower = message.lower().strip()
    
    # 1. System map context is ALWAYS relevant
    if "[system map context" in message_lower:
        return True

    # 2. Greetings, thanks, identity & profile queries are ALWAYS relevant
    if re.search(r'\b(hi+|hello+|hey+|namaste|hola|greetings|good\s+morning|good\s+afternoon|good\s+evening|yo|sup|howdy|thanks|thank\s+you)\b', message_lower):
        return True
    
    allowed_greetings = {"hi", "hello", "hey", "hola", "namaste", "thanks", "thank you", "help", "who are you", "what is your name", "what can you do", "who am i", "my name"}
    if message_lower in allowed_greetings or any(g in message_lower for g in ["how are you", "who are you", "what can you", "what is your name", "who am i", "my name", "my booking", "my ticket", "my stay", "my profile", "my trip", "current trip", "active trip", "where am i going", "where i am going"]):
        return True
        
    # 3. Explicitly reject off-topic general knowledge, politics & coding queries
    off_topic_patterns = [
        r'\bwho\s+is\b', r'\bprime\s+minister\b', r'\bpresident\b', r'\bpolitician\b', r'\bpolitics\b',
        r'\bmath\b', r'\bscience\b', r'\bphysics\b', r'\bchemistry\b', r'\bhistory\b', r'\bcapital\s+of\b',
        r'\bwrite\s+code\b', r'\bpython\b', r'\bjavascript\b', r'\bjava\b'
    ]
    for pattern in off_topic_patterns:
        if re.search(pattern, message_lower) and not any(allowed in message_lower for allowed in ["who am i", "who are you"]):
            return False

    # 4. Travel & RoadBuddy core keywords
    keywords = [
        "trip", "trips", "travel", "road", "route", "routes", "highway", "nh-", "nh ", "hotel", "hotels", "dhaba", "dhabas", "restaurant", "restaurants", "food", 
        "fuel", "toll", "tolls", "cost", "costs", "budget", "price", "prices", "km", "mile", "car", "bike", "vehicle", "vehicles", "cab", "cabs", "bus", "buses", 
        "train", "trains", "flight", "flights", "destination", "origin", "map", "maps", "navigate", "navigation", "compass", "itinerary", 
        "pack", "weather", "booking", "bookings", "tourist", "visit", "attraction", "sightseeing", "driver", "passenger", 
        "seat", "seats", "stay", "room", "city", "state", "india", "ticket", "tickets", "planner", "buddy", "drive", "ride",
        "himalay", "goa", "jaipur", "udaipur", "delhi", "mumbai", "manali", "tour", "place", "location", "distance",
        "gas", "petrol", "diesel", "ev ", "charging"
    ]
    return any(kw in message_lower for kw in keywords)


def mock_chat_response(message: str, user_context: str = None) -> str:
    message_lower = message.lower()
    
    if user_context and any(word in message_lower for word in ["booking", "bookings", "hotel", "bus", "train", "flight", "cab", "transit", "reservation", "ticket"]):
        lines = [line.strip() for line in user_context.split("\n") if line.strip()]
        bookings = [line for line in lines if "booking" in line.lower() or "transit" in line.lower()]
        
        # Filter for specific modes if asked
        for mode in ["hotel", "bus", "train", "flight", "cab", "transit"]:
            if mode in message_lower:
                bookings = [b for b in bookings if mode.lower() in b.lower()]
                
        if bookings:
            # Check if specifically asking about stops/duration or complimentary/meals
            is_stops_query = any(w in message_lower for w in ["stop", "stops", "duration", "time", "where", "how long"])
            is_comp_query = any(w in message_lower for w in ["complimentary", "free", "meal", "meals", "amenities", "wifi", "include", "inclusions"])
            
            resp_lines = []
            for b in bookings:
                if is_stops_query:
                    # extract stops if present
                    if "stops" in b.lower():
                        parts = b.split(". ")
                        stop_part = [p for p in parts if "stops" in p.lower()]
                        if stop_part:
                            resp_lines.append(f"📍 {stop_part[0]}")
                        else:
                            resp_lines.append(b)
                    else:
                        resp_lines.append(b)
                elif is_comp_query:
                    # extract complimentary if present
                    if "complimentary" in b.lower() or "amenities" in b.lower():
                        parts = b.split(". ")
                        comp_part = [p for p in parts if "complimentary" in p.lower() or "amenities" in p.lower()]
                        if comp_part:
                            resp_lines.append(f"🎁 {'. '.join(comp_part)}")
                        else:
                            resp_lines.append(b)
                    else:
                        resp_lines.append(b)
                else:
                    resp_lines.append(b)
                    
            return "📋 Here are your active booking details:\n" + "\n".join(resp_lines)
        else:
            return "🔍 I checked your profile, but you don't have any active bookings yet! Let me know if you want to book one. 🚗"
            
    if user_context and any(word in message_lower for word in ["my name", "who am i", "my email", "profile", "my details", "what is my name"]):
        lines = [line.strip() for line in user_context.split("\n") if line.strip()]
        user_lines = [line for line in lines if "user name:" in line.lower() or "user email:" in line.lower()]
        if user_lines:
            return "👤 Here are your profile details:\n" + "\n".join([f"- {l}" for l in user_lines])
            
    if user_context and any(word in message_lower for word in ["vehicle", "vehicles", "car", "bike"]):
        lines = [line.strip() for line in user_context.split("\n") if line.strip()]
        veh_lines = [line for line in lines if "vehicle:" in line.lower()]
        if veh_lines:
            return "🚗 Here are your registered vehicles:\n" + "\n".join([f"{v}" for v in veh_lines])
        else:
            return "🔍 I checked your profile, but you don't have any registered vehicles yet! You can add one under My Vehicles. 🚗"
            
    if user_context and any(word in message_lower for word in ["trip", "trips", "itinerary", "route", "routes", "active trip", "current trip", "my trip"]):
        lines = [line.strip() for line in user_context.split("\n") if line.strip()]
        trip_lines = [line for line in lines if "trip:" in line.lower()]
        if trip_lines:
            return "🗺️ Here are your active trip details:\n" + "\n".join([f"• {t}" for t in trip_lines])
        else:
            return "🔍 I checked your profile, but you don't have any active trips recorded yet! Let's plan one together. 🚗"

    if any(word in message_lower for word in ["hi", "hello", "hey", "namaste", "hola", "greetings"]):
        return ("👋 Hello! I am RoadBuddy AI, your friendly road trip assistant. "
                "How can I help you plan your journey, check bookings, or find best routes today? 🚗")
    elif any(word in message_lower for word in ["thank", "thanks"]):
        return "😊 You're very welcome! Let me know if you need help with anything else. Safe travels! 🚗"
    elif any(word in message_lower for word in ["jaipur", "rajasthan"]):
        return ("🏰 Jaipur is a fantastic base for road trips! From Jaipur you can reach Ajmer (135 km via NH-48), "
                "Udaipur (393 km via NH-48), Ranthambore (180 km via NH-52). "
                "A 3-day Jaipur to Udaipur trip costs Rs 8,000-12,000 for 2 people. What type of trip are you planning? 🚗")
    elif any(word in message_lower for word in ["budget", "cost", "price"]):
        return ("💰 Rough budget breakdown: Fuel Rs 3-5 per km. Budget hotel Rs 800-1500/night. "
                "Food Rs 300-600 per person at dhabas. Tolls Rs 200-800. "
                "Tell me your origin, destination and days for an exact estimate! 🎯")
    elif any(word in message_lower for word in ["manali", "himachal", "mountain"]):
        return ("🏔️ Manali is amazing! Best time: Oct-Nov and Mar-Jun. From Delhi: 540 km via NH-44. "
                "Budget for 4 days: Rs 15,000-25,000 for 2 people. "
                "Top spots: Solang Valley, Rohtang Pass, Hadimba Temple. Want a detailed plan? 😊")
    else:
        return ("🚗 I'm RoadBuddy AI, your Indian road trip expert! "
                "I can help with trip planning, budget estimation, best routes, hotels, food, and seasonal tips. "
                "Try: 'Plan a 3-day trip from Jaipur to Udaipur for 2 people' 😊")


from app.services.groq_client import call_groq_native, call_gemini_native

async def call_groq_chat(messages: list[dict], user_context: str = None) -> str:
    sys_prompt = SYSTEM_PROMPT
    if user_context:
        sys_prompt += f"\n\n[USER CONTEXT]\nThe user is logged in. Use this context to answer questions about their name, profile, registered vehicles, active trips, and booking details (hotels, buses, trains, flights, cabs, transits). Be specific and match their queries with these details:\n{user_context}"
    combined_messages = [{"role": "system", "content": sys_prompt}] + messages
    
    # Try Groq API first
    if settings.groq_api_key.strip():
        try:
            return await call_groq_native(combined_messages, temperature=0.8, max_tokens=1000)
        except Exception as e:
            print(f"Groq native chat failed ({e}). Falling back to Gemini.")
            
    # Fallback to Gemini API
    return await call_gemini_native(combined_messages, temperature=0.8, max_tokens=1000)


def lookup_details_by_id(db, record_id: int) -> str:
    from app.models.models import User, Vehicle, Trip, TripStop, Booking, HotelBooking, ProviderBooking, ProviderVehicle, Provider
    
    # 1. Booking (Transit Booking)
    booking = db.query(Booking).filter(Booking.id == record_id).first()
    if booking:
        try:
            from app.services.transport_service import get_transport_option_by_id, get_transit_stops_and_amenities
            opt = get_transport_option_by_id(booking.transport_option_id, db)
            mode = opt.mode if opt else "Transit"
            operator = opt.operator if opt else "RoadBuddy Partner"
            origin = opt.origin if opt else "N/A"
            destination = opt.destination if opt else "N/A"
            stops, items = get_transit_stops_and_amenities(origin, destination, mode, operator, booking.transport_option_id)
            stops_str = ", ".join([f"{s['name']} ({s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            return (
                f"🎫 **Booking ID {record_id} Details**:\n"
                f"- **Passenger**: {booking.passenger_name}\n"
                f"- **Mode**: {mode.upper()}\n"
                f"- **Operator**: {operator}\n"
                f"- **Route**: {origin} to {destination}\n"
                f"- **Travel Date**: {booking.travel_date}\n"
                f"- **Seats**: {booking.selected_seats or 'Auto-assigned'}\n"
                f"- **Class**: {booking.travel_class or 'Standard'}\n"
                f"- **Fare Paid**: ₹{booking.total_fare_inr:.0f}\n"
                f"- **Status**: {booking.status.upper()}\n"
                f"- **Intermediate Stops**: {stops_str}\n"
                f"- **Complimentary Inclusions**: {items_str}"
            )
        except Exception as e:
            pass

    # 2. ProviderBooking (Cab Booking)
    p_booking = db.query(ProviderBooking).filter(ProviderBooking.id == record_id).first()
    if p_booking:
        try:
            from app.services.transport_service import get_transit_stops_and_amenities
            v_name = p_booking.vehicle.vehicle_name if p_booking.vehicle else "Cab"
            provider_name = p_booking.vehicle.provider.company_name if (p_booking.vehicle and p_booking.vehicle.provider) else "Cab Provider"
            p_loc = p_booking.pickup_location or "N/A"
            d_loc = p_booking.dropoff_location or "N/A"
            p_name = p_loc.split("|||")[0] if "|||" in p_loc else p_loc
            d_name = d_loc.split("|||")[0] if "|||" in d_loc else d_loc
            stops, items = get_transit_stops_and_amenities(p_name, d_name, "cab", v_name, f"cab_{p_booking.vehicle_id}")
            stops_str = ", ".join([f"{s['name']} ({s['duration_mins']} mins)" for s in stops]) if stops else "Direct (no stops)"
            items_str = ", ".join(items) if items else "Standard amenities"
            return (
                f"🚖 **Cab Booking ID {record_id} Details**:\n"
                f"- **Passenger**: {p_booking.passenger_name} ({p_booking.passenger_phone or 'N/A'})\n"
                f"- **Vehicle**: {v_name} (with {provider_name})\n"
                f"- **Route**: {p_name} to {d_name}\n"
                f"- **Travel Date**: {p_booking.travel_date}\n"
                f"- **Seats**: {p_booking.selected_seats or p_booking.num_seats}\n"
                f"- **Fare Paid**: ₹{p_booking.total_fare_inr:.0f}\n"
                f"- **Status**: {p_booking.status.upper()}\n"
                f"- **Intermediate Stops**: {stops_str}\n"
                f"- **Complimentary Inclusions**: {items_str}"
            )
        except Exception as e:
            pass

    # 3. Trip
    trip = db.query(Trip).filter(Trip.id == record_id).first()
    if trip:
        stops = db.query(TripStop).filter(TripStop.trip_id == trip.id).order_by(TripStop.day, TripStop.time_slot).all()
        stops_str = ", ".join([f"Day {s.day} {s.time_slot}: {s.place_name} ({s.place_type})" for s in stops]) if stops else "No stops"
        return (
            f"🗺️ **Trip ID {record_id} Details**:\n"
            f"- **Route**: {trip.origin} to {trip.destination}\n"
            f"- **Dates**: {trip.start_date} to {trip.end_date or 'N/A'}\n"
            f"- **Travel Mode**: {trip.travel_mode}\n"
            f"- **Budget**: ₹{trip.budget_inr:.0f}\n"
            f"- **Total Estimated Cost**: ₹{trip.total_cost_inr:.0f}\n"
            f"- **Stops**: {stops_str}\n"
            f"- **AI Summary**: {trip.ai_summary or 'None'}"
        )

    # 4. ProviderVehicle (listed vehicle)
    p_vehicle = db.query(ProviderVehicle).filter(ProviderVehicle.id == record_id).first()
    if p_vehicle:
        status = "Active" if p_vehicle.is_active else "Inactive"
        fare_parts = []
        if p_vehicle.fixed_fare_inr:
            fare_parts.append(f"Fixed Fare: ₹{int(p_vehicle.fixed_fare_inr)}")
        if p_vehicle.price_per_km_inr:
            fare_parts.append(f"Price per KM: ₹{p_vehicle.price_per_km_inr}")
        fare_str = " / ".join(fare_parts) if fare_parts else "N/A"
        return (
            f"🚙 **Vehicle Listing ID {record_id} Details**:\n"
            f"- **Name**: {p_vehicle.vehicle_name} ({p_vehicle.vehicle_type.upper()})\n"
            f"- **Route**: {p_vehicle.origin} to {p_vehicle.destination}\n"
            f"- **Fares**: {fare_str}\n"
            f"- **Timings**: Departs {p_vehicle.departure_time or 'N/A'} · Arrives {p_vehicle.arrival_time or 'N/A'}\n"
            f"- **Stops**: Pickup: {p_vehicle.pickup_points or 'Origin'} · Drop-off: {p_vehicle.dropoff_points or 'Destination'}\n"
            f"- **Seats**: {p_vehicle.seats_booked}/{p_vehicle.total_seats} booked\n"
            f"- **Service Dates**: {p_vehicle.service_dates or 'Daily'}\n"
            f"- **Status**: {status}"
        )

    # 5. HotelBooking
    h_booking = db.query(HotelBooking).filter(HotelBooking.id == record_id).first()
    if h_booking:
        hotel_name = h_booking.hotel.name if h_booking.hotel else "Hotel"
        hotel_city = h_booking.hotel.city if h_booking.hotel else "Unknown"
        hotel_amenities = h_booking.hotel.amenities if (h_booking.hotel and h_booking.hotel.amenities) else "WiFi, AC"
        return (
            f"🏨 **Hotel Booking ID {record_id} Details**:\n"
            f"- **Hotel**: {hotel_name} ({hotel_city})\n"
            f"- **Check-in**: {h_booking.check_in_date}\n"
            f"- **Check-out**: {h_booking.check_out_date}\n"
            f"- **Rooms / Guests**: {h_booking.num_rooms} Room(s) / {h_booking.num_guests} Guest(s)\n"
            f"- **Price Paid**: ₹{h_booking.total_price_inr:.0f}\n"
            f"- **Status**: {h_booking.status.upper()}\n"
            f"- **Amenities**: {hotel_amenities}"
        )

    # 6. Vehicle (traveler registered vehicle)
    vehicle = db.query(Vehicle).filter(Vehicle.id == record_id).first()
    if vehicle:
        return (
            f"🚗 **Traveler Vehicle ID {record_id} Details**:\n"
            f"- **Name**: {vehicle.name}\n"
            f"- **Category**: {vehicle.category}\n"
            f"- **Fuel Type**: {vehicle.fuel_type}\n"
            f"- **Mileage**: {vehicle.mileage_kmpl} kmpl"
        )

    # 7. User
    user = db.query(User).filter(User.id == record_id).first()
    if user:
        return (
            f"👤 **User ID {record_id} Details**:\n"
            f"- **Name**: {user.name}\n"
            f"- **Email**: {user.email}\n"
            f"- **Status**: Registered Traveler"
        )

    # 8. Provider
    provider = db.query(Provider).filter(Provider.id == record_id).first()
    if provider:
        return (
            f"🚐 **Provider Partner ID {record_id} Details**:\n"
            f"- **Company**: {provider.company_name or 'N/A'}\n"
            f"- **Contact Person**: {provider.contact_person or 'N/A'}\n"
            f"- **Email**: {provider.email}\n"
            f"- **Phone**: {provider.phone or 'N/A'}\n"
            f"- **City**: {provider.city or 'N/A'}\n"
            f"- **Service Type**: {provider.service_type or 'N/A'}"
        )

    return None


def execute_chatbot_booking(trigger_data: dict, user_id: int, db) -> str:
    import datetime
    booking_type = trigger_data.get("type", "").lower()
    if not user_id or not db:
        return "⚠️ Error: Unable to complete booking. User is not authenticated."

    try:
        if booking_type == "hotel":
            from app.models.models import Hotel, HotelBooking
            city = trigger_data.get("city", "").strip()
            name = trigger_data.get("name", "").strip()
            
            hotel = None
            if name and city:
                hotel = db.query(Hotel).filter(Hotel.city.ilike(f"%{city}%"), Hotel.name.ilike(f"%{name}%")).first()
            if not hotel and city:
                hotel = db.query(Hotel).filter(Hotel.city.ilike(f"%{city}%")).first()
            if not hotel:
                hotel = db.query(Hotel).first()
            
            if not hotel:
                hotel = Hotel(
                    name=name or "Grand Palace Stay",
                    city=city or "Jaipur",
                    address=f"Mall Road, {city or 'Jaipur'}",
                    star_rating=4.0,
                    price_per_night_inr=3000.0,
                    total_rooms=40,
                    rooms_booked=0,
                    amenities="WiFi, AC, Restaurant"
                )
                db.add(hotel)
                db.commit()
                db.refresh(hotel)

            check_in = trigger_data.get("date") or trigger_data.get("check_in") or datetime.date.today().isoformat()
            check_out = trigger_data.get("check_out") or (datetime.date.fromisoformat(check_in) + datetime.timedelta(days=1)).isoformat()
            rooms = int(trigger_data.get("rooms", 1))
            guests = int(trigger_data.get("guests", 2))
            
            try:
                d1 = datetime.date.fromisoformat(check_in)
                d2 = datetime.date.fromisoformat(check_out)
                nights = max((d2 - d1).days, 1)
            except Exception:
                nights = 1
                
            total_price = hotel.price_per_night_inr * rooms * nights
            
            booking = HotelBooking(
                hotel_id=hotel.id,
                user_id=user_id,
                check_in_date=check_in,
                check_out_date=check_out,
                num_rooms=rooms,
                num_guests=guests,
                total_price_inr=total_price,
                status="confirmed"
            )
            hotel.rooms_booked += rooms
            db.add(booking)
            db.commit()
            db.refresh(booking)
            
            return f"🏨 **Hotel Booked successfully!**\n- **Hotel**: {hotel.name} ({hotel.city})\n- **Check-in**: {check_in}\n- **Check-out**: {check_out}\n- **Rooms**: {rooms}\n- **Booking ID**: #{booking.id}"

        elif booking_type in ("bus", "train", "flight"):
            from app.models.models import TransportOption, Booking, User
            origin = trigger_data.get("origin", "").strip()
            destination = trigger_data.get("destination", "").strip()
            travel_date = trigger_data.get("date") or datetime.date.today().isoformat()
            selected_seats = trigger_data.get("seats") or "Auto-assigned"
            travel_class = trigger_data.get("class") or "Standard"
            
            opt = None
            if origin and destination:
                opt = db.query(TransportOption).filter(
                    TransportOption.mode == booking_type,
                    TransportOption.origin.ilike(f"%{origin}%"),
                    TransportOption.destination.ilike(f"%{destination}%")
                ).first()
            if not opt:
                opt = db.query(TransportOption).filter(TransportOption.mode == booking_type).first()
                
            if not opt:
                opt = TransportOption(
                    origin=origin or "Delhi",
                    destination=destination or "Jaipur",
                    mode=booking_type,
                    operator=trigger_data.get("name") or f"RoadBuddy {booking_type.title()}",
                    departure_time="10:00",
                    arrival_time="16:00",
                    duration_hrs=6.0,
                    fare_inr=1500.0,
                    seats_available=100
                )
                db.add(opt)
                db.commit()
                db.refresh(opt)
                
            user = db.query(User).filter(User.id == user_id).first()
            passenger_name = user.name if user else "Passenger"
            
            booking = Booking(
                user_id=user_id,
                transport_option_id=f"{booking_type}_{opt.id}",
                passenger_name=passenger_name,
                travel_date=travel_date,
                include_return=False,
                going_fare_inr=opt.fare_inr,
                return_fare_inr=0.0,
                total_fare_inr=opt.fare_inr,
                status="confirmed",
                selected_seats=selected_seats,
                travel_class=travel_class
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            
            try:
                if booking_type == "bus":
                    from app.models.models import Bus
                    bus = db.query(Bus).filter(Bus.id == opt.id).first()
                    if bus:
                        bus.seats_booked += 1
                        db.commit()
                elif booking_type == "train":
                    from app.models.models import Train
                    train = db.query(Train).filter(Train.id == opt.id).first()
                    if train:
                        train.seats_booked += 1
                        db.commit()
                elif booking_type == "flight":
                    from app.models.models import Flight
                    flight = db.query(Flight).filter(Flight.id == opt.id).first()
                    if flight:
                        flight.seats_booked += 1
                        db.commit()
            except Exception:
                pass
                
            icon = {"bus": "🚌", "train": "🚂", "flight": "✈️"}[booking_type]
            return f"{icon} **{booking_type.title()} Ticket Booked successfully!**\n- **Operator**: {opt.operator}\n- **Route**: {opt.origin} → {opt.destination}\n- **Date**: {travel_date}\n- **Seats**: {selected_seats}\n- **Class**: {travel_class}\n- **Booking ID**: #{booking.id}"

        elif booking_type == "cab":
            from app.models.models import ProviderVehicle, ProviderBooking, User, Provider
            origin = trigger_data.get("origin", "").strip()
            destination = trigger_data.get("destination", "").strip()
            travel_date = trigger_data.get("date") or datetime.date.today().isoformat()
            
            v = None
            if origin and destination:
                v = db.query(ProviderVehicle).filter(
                    ProviderVehicle.origin.ilike(f"%{origin}%"),
                    ProviderVehicle.destination.ilike(f"%{destination}%"),
                    ProviderVehicle.is_active == True
                ).first()
            if not v:
                v = db.query(ProviderVehicle).filter(ProviderVehicle.is_active == True).first()
                
            if not v:
                provider = db.query(Provider).first()
                if not provider:
                    provider = Provider(
                        company_name="RoadBuddy Cabs Ltd.",
                        contact_person="Ravi Kumar",
                        email="cabs@roadbuddy.in",
                        password_hash="dummy"
                    )
                    db.add(provider)
                    db.commit()
                    db.refresh(provider)
                    
                v = ProviderVehicle(
                    provider_id=provider.id,
                    vehicle_type="sedan",
                    vehicle_name="Swift Dzire",
                    origin=origin or "Jaipur",
                    destination=destination or "Udaipur",
                    fixed_fare_inr=3000.0,
                    total_seats=4,
                    seats_booked=0,
                    is_active=True
                )
                db.add(v)
                db.commit()
                db.refresh(v)
                
            user = db.query(User).filter(User.id == user_id).first()
            passenger_name = user.name if user else "Passenger"
            passenger_email = user.email if user else "passenger@roadbuddy.in"
            
            booking = ProviderBooking(
                vehicle_id=v.id,
                user_id=user_id,
                passenger_name=passenger_name,
                passenger_phone="9876543210",
                passenger_email=passenger_email,
                travel_date=travel_date,
                num_seats=1,
                pickup_location=origin or v.origin,
                dropoff_location=destination or v.destination,
                total_fare_inr=v.fixed_fare_inr or 3000.0,
                status="confirmed"
            )
            v.seats_booked += 1
            db.add(booking)
            db.commit()
            db.refresh(booking)
            
            return f"🚖 **Cab Booking Confirmed!**\n- **Cab**: {v.vehicle_name}\n- **Route**: {booking.pickup_location} → {booking.dropoff_location}\n- **Date**: {travel_date}\n- **Booking ID**: #{booking.id}"

        else:
            return "⚠️ Error: Unknown booking type requested."

    except Exception as e:
        return f"⚠️ Error executing booking: {str(e)}"


def format_json_response_to_text(response_text: str) -> str:
    cleaned = response_text.strip()
    if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
        if "[BOOKING_TRIGGER:" in response_text:
            return response_text
            
        try:
            import json
            data = json.loads(cleaned)
            
            if isinstance(data, dict):
                parts = []
                
                trip_info = data.get("trip_details") or data
                if isinstance(trip_info, dict):
                    orig = trip_info.get("origin") or trip_info.get("from")
                    dest = trip_info.get("destination") or trip_info.get("to")
                    if orig and dest:
                        parts.append(f"📍 **Route**: {orig} → {dest}")
                    elif "current_trip" in trip_info:
                        parts.append(f"🗺️ **Current Trip**: {trip_info['current_trip']}")
                        
                    dates = trip_info.get("trip_dates") or trip_info.get("dates")
                    if dates:
                        if isinstance(dates, list):
                            parts.append(f"🗓️ **Trip Dates**: {' to '.join(dates)}")
                        else:
                            parts.append(f"🗓️ **Trip Dates**: {dates}")
                            
                    mode = trip_info.get("travel_mode") or trip_info.get("mode")
                    if mode:
                        parts.append(f"🚗 **Travel Mode**: {str(mode).replace('_', ' ').title()}")
                        
                    vehicle = trip_info.get("vehicle")
                    if vehicle:
                        parts.append(f"🚘 **Vehicle**: {vehicle}")
                        
                    cost = trip_info.get("total_cost") or trip_info.get("total_estimated_cost") or trip_info.get("budget")
                    if cost:
                        parts.append(f"💰 **Estimated Budget / Cost**: ₹{cost}")

                highways = data.get("route_highways") or data.get("highways")
                if highways and isinstance(highways, list):
                    h_list = []
                    for h in highways:
                        if isinstance(h, dict):
                            h_name = h.get("highway") or h.get("name") or "Highway"
                            h_dir = h.get("direction") or ""
                            h_list.append(f"{h_name} ({h_dir})" if h_dir else h_name)
                        elif isinstance(h, str):
                            h_list.append(h)
                    if h_list:
                        parts.append(f"🛣️ **Highways**: {', '.join(h_list)}")

                curr_loc = data.get("current_location")
                if curr_loc and curr_loc != "null" and curr_loc is not None:
                    parts.append(f"📍 **Current Location**: {curr_loc}")

                next_dest = data.get("next_destination")
                if next_dest and next_dest != "null" and next_dest is not None:
                    parts.append(f"🎯 **Next Destination**: {next_dest}")

                if parts:
                    return "Here are your active trip details:\n\n" + "\n".join(parts)
                
                lines = []
                def parse_obj(obj, indent=0):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if v is None or v == "null":
                                continue
                            label = k.replace("_", " ").title()
                            if isinstance(v, (dict, list)):
                                lines.append(f"{'  '*indent}• **{label}**:")
                                parse_obj(v, indent + 1)
                            else:
                                lines.append(f"{'  '*indent}• **{label}**: {v}")
                    elif isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, (dict, list)):
                                parse_obj(item, indent)
                            else:
                                lines.append(f"{'  '*indent}- {item}")

                parse_obj(data)
                if lines:
                    return "\n".join(lines)
        except Exception as e:
            print(f"JSON format fallback error: {e}")
            pass
    return response_text


def strip_unnecessary_greetings(text: str, is_pure_greeting: bool = False) -> str:
    if is_pure_greeting:
        return text
    import re
    cleaned = re.sub(r'(?:Hey|Hello|Hi)\s+[A-Za-z0-9_\-\.]+(?:,|\!|\.)?\s*', '', text, flags=re.IGNORECASE).strip()
    if cleaned and cleaned[0].islower():
        return cleaned[0].upper() + cleaned[1:]
    return cleaned or text


async def chat_with_roadbuddy(message: str, history: list[dict] = None, user_context: str = None, db = None, user_id: int = None) -> dict:
    try:
        raw_history = history or []
        filtered_history = [h for h in raw_history if h.get("role") in ("user", "assistant")]
        truncated_history = filtered_history[-10:]
        
        msg_clean = message.lower().strip()
        import re

        # Confidentiality Guard Clause: Protect source code & internal tech stack details
        code_tech_keywords = [
            "what ai", "which ai", "ai model", "ai tech", "ai technology", "ai ur using", "ai you using", 
            "project code", "source code", "codebase", "tell me code", "code of this", "code of project", "cod3",
            "tech stack", "technology stack", "llm", "backend", "groq", "gemini", "llama", "system prompt", "architecture"
        ]
        if any(kw in msg_clean for kw in code_tech_keywords):
            response_text = "I am RoadBuddy AI, your road trip assistant! I am here to help you plan trips, navigate highways, find dhabas, and manage your travel bookings. 🚗"
            updated_history = truncated_history + [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}]
            return {"response": response_text, "history": updated_history, "total_messages": len(updated_history)}

        is_pure_greeting = bool(re.match(r'^(hi+|hello+|hey+|namaste|hola|greetings|good\s+morning|good\s+afternoon|good\s+evening|yo|sup|howdy)[!\.\?\s]*$', msg_clean))
        is_pure_thanks = bool(re.match(r'^(thank+|thanks|thank\s+you)[!\.\?\s]*$', msg_clean))
        
        if is_pure_greeting:
            user_name = "traveler"
            active_info = ""
            if user_context:
                for line in user_context.split("\n"):
                    if line.startswith("User Name:") and len(line.split(":")) > 1:
                        user_name = line.split(":")[1].strip()
                    elif ("Trip:" in line or "User Trips:" in line) and not active_info:
                        active_info = line.strip()
                    elif ("Booking:" in line or "Transit" in line) and not active_info:
                        active_info = line.strip()

            if active_info:
                response_text = f"👋 Hello {user_name}! I am RoadBuddy AI, your friendly road trip assistant. How can I help you plan your journey, check bookings, or find best routes today? 🚗"
            else:
                response_text = f"👋 Hello {user_name}! I am RoadBuddy AI, your friendly road trip assistant. How can I help you plan your journey, check bookings, or find best routes today? 🚗"

            updated_history = truncated_history + [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}]
            return {"response": response_text, "history": updated_history, "total_messages": len(updated_history)}
            
        elif is_pure_thanks:
            response_text = "😊 You're very welcome! Let me know if you need help with anything else. Safe travels! 🚗"
            updated_history = truncated_history + [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}]
            return {"response": response_text, "history": updated_history, "total_messages": len(updated_history)}

        has_lookup_keyword = any(kw in msg_clean for kw in ["booking", "id", "ref", "reference", "ticket", "details", "lookup", "track", "show", "view"]) or msg_clean.startswith("#")
        if db and has_lookup_keyword:
            is_explicit_id = re.search(r'\b(?:booking|id|ref|reference|ticket|#)\s*\d+\b', msg_clean) or re.match(r'^#?\d+$', msg_clean)
            if is_explicit_id:
                raw_ids = [int(x) for x in re.findall(r'\b\d+\b', msg_clean)]
                for rid in raw_ids:
                    details = lookup_details_by_id(db, rid)
                    if details:
                        updated_history = truncated_history + [{"role": "user", "content": message}, {"role": "assistant", "content": details}]
                        return {"response": details, "history": updated_history, "total_messages": len(updated_history)}

        if not is_relevant_query(message):
            response_text = DEFAULT_REJECTION_MESSAGE
            updated_history = truncated_history + [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}]
            return {"response": response_text, "history": updated_history, "total_messages": len(updated_history)}
            
        messages = truncated_history + [{"role": "user", "content": message}]
        if db:
            db.rollback()
        if settings.gemini_api_key or settings.groq_api_key:
            try:
                response_text = await call_groq_chat(messages, user_context)
            except Exception as e:
                print(f"Groq chat failed: {e}. Falling back to mock chat response.")
                response_text = mock_chat_response(message, user_context)
        else:
            response_text = mock_chat_response(message, user_context)

        # Sanitize any raw JSON blocks returned by LLMs into natural text
        response_text = format_json_response_to_text(response_text)
        # Strip repetitive name greetings on non-greeting question turns
        response_text = strip_unnecessary_greetings(response_text, is_pure_greeting)

        # Intercept booking trigger in response_text
        if "[BOOKING_TRIGGER:" in response_text:
            try:
                import json
                start_idx = response_text.find("[BOOKING_TRIGGER:")
                end_idx = response_text.find("]", start_idx)
                if end_idx != -1:
                    trigger_json_str = response_text[start_idx + len("[BOOKING_TRIGGER:"):end_idx].strip()
                    trigger_data = json.loads(trigger_json_str)
                    
                    # Execute booking
                    booking_conf = execute_chatbot_booking(trigger_data, user_id, db)
                    
                    # Replace trigger in response
                    response_text = response_text[:start_idx] + booking_conf + response_text[end_idx + 1:]
            except Exception as e:
                print(f"Failed to process booking trigger: {e}")

        updated_history = messages + [{"role": "assistant", "content": response_text}]
        return {"response": response_text, "history": updated_history, "total_messages": len(updated_history)}
    except Exception as e:
        raise RuntimeError(f"Chat failed: {e}") from e