from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.provider.router import router as provider_router
from fastapi.middleware.cors import CORSMiddleware
from app.provider.pages import router as provider_pages_router
from app.provider.food_pages import router as food_provider_pages_router
from app.routers import booking, payment

from app.routers import trips, fuel, users, community, journal, transport, food, auth, stations, search
from app.routers import fuel_operator_pages
from app.pages import auth_pages, dashboard_pages
from app.core.database import engine
from sqlalchemy import text
from app.core.config import settings

app = FastAPI(
    title="RoadBuddy AI",
    description="India's Ultimate Road Trip Companion — API Backend",
    version="1.0.0",
)

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        if request.url.path.startswith("/api"):
            return JSONResponse(status_code=404, content={"detail": exc.detail})
        
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        user = None
        try:
            from app.core.database import SessionLocal
            from app.pages.dashboard_pages import get_user_from_cookie
            db = SessionLocal()
            user = get_user_from_cookie(request, db)
            db.close()
        except Exception:
            pass
        return templates.TemplateResponse(request, "404.html", {"user": user}, status_code=404)
    
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return HTMLResponse(content=f"<h1>Error {exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)

@app.exception_handler(Exception)
async def custom_global_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    user = None
    try:
        from app.core.database import SessionLocal
        from app.pages.dashboard_pages import get_user_from_cookie
        db = SessionLocal()
        user = get_user_from_cookie(request, db)
        db.close()
    except Exception:
        pass
    return templates.TemplateResponse(request, "500.html", {"user": user, "error": str(exc) if settings.debug else "Internal Server Error"}, status_code=500)

# Run schema updates on startup
@app.on_event("startup")
async def run_migrations():
    from app.models.models import Base
    Base.metadata.create_all(bind=engine)
    statements = [
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS alternate_email VARCHAR;",
        "ALTER TABLE providers ADD COLUMN IF NOT EXISTS booking_mode VARCHAR;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS arrival_time VARCHAR;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS pickup_points VARCHAR;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS dropoff_points VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS dropoff_location VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS selected_seats VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS passenger_phone VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS passenger_email VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS navigation_status VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS driver_lat FLOAT;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS driver_lon FLOAT;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS message_unread BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS service_dates VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS passenger_details VARCHAR;",
        "ALTER TABLE provider_bookings ADD COLUMN IF NOT EXISTS provider_unread BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS end_date VARCHAR;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS group_type VARCHAR;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS num_people INTEGER DEFAULT 1;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_lat FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_lon FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destination_lat FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destination_lon FLOAT;",
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS selected_seats VARCHAR;",
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS travel_class VARCHAR;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active';",
        "ALTER TABLE hotels ADD COLUMN IF NOT EXISTS avg_rating FLOAT DEFAULT 0.0;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS avg_rating FLOAT DEFAULT 0.0;",
        "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS total_reviews INTEGER DEFAULT 0;",
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS duffel_order_id VARCHAR;",
        "ALTER TABLE hotel_bookings ADD COLUMN IF NOT EXISTS duffel_booking_id VARCHAR;",
        "ALTER TABLE fuel_station_operators ADD COLUMN IF NOT EXISTS email VARCHAR;",
        "ALTER TABLE fuel_station_operators ALTER COLUMN station_id DROP NOT NULL;",
        "ALTER TABLE fuel_station_operators ALTER COLUMN phone_number DROP NOT NULL;",
        "ALTER TABLE fuel_station_operators ADD COLUMN IF NOT EXISTS relationship_to_pump VARCHAR;",
        "ALTER TABLE fuel_station_operators ADD COLUMN IF NOT EXISTS gov_id VARCHAR;",
        "ALTER TABLE fuel_station_operators ADD COLUMN IF NOT EXISTS dealership_agreement_number VARCHAR;",
        "ALTER TABLE fuel_stations ADD COLUMN IF NOT EXISTS gstin VARCHAR;",
        "ALTER TABLE fuel_stations ADD COLUMN IF NOT EXISTS location_verified BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE availability_updates ADD COLUMN IF NOT EXISTS ttl_hours FLOAT;"
    ]
    with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "sqlite":
            create_assets_table = """
            CREATE TABLE IF NOT EXISTS provider_vehicle_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                vehicle_type VARCHAR NOT NULL,
                vehicle_name VARCHAR NOT NULL,
                driver_included BOOLEAN DEFAULT 1,
                total_seats INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(provider_id) REFERENCES providers(id)
            );
            """
        else:
            create_assets_table = """
            CREATE TABLE IF NOT EXISTS provider_vehicle_assets (
                id SERIAL PRIMARY KEY,
                provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                vehicle_type VARCHAR NOT NULL,
                vehicle_name VARCHAR NOT NULL,
                driver_included BOOLEAN DEFAULT TRUE,
                total_seats INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        try:
            connection.execute(text(create_assets_table))
        except Exception as e:
            print(f"Failed to create provider_vehicle_assets table: {e}")

        for stmt in statements:
            stmt_to_exec = stmt
            if dialect == "sqlite":
                stmt_to_exec = stmt.replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")
            try:
                connection.execute(text(stmt_to_exec))
            except Exception as e:
                if "duplicate column name" not in str(e).lower() and "already exists" not in str(e).lower():
                    print(f"Schema update statement skipped: {stmt_to_exec}. Reason: {e}")

        stmt_asset = "ALTER TABLE provider_vehicles ADD COLUMN IF NOT EXISTS vehicle_asset_id INTEGER;"
        if dialect == "sqlite":
            stmt_asset = stmt_asset.replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")
        try:
            connection.execute(text(stmt_asset))
        except Exception as e:
            if "duplicate column name" not in str(e).lower() and "already exists" not in str(e).lower():
                print(f"Failed to add vehicle_asset_id to provider_vehicles: {e}")

        if dialect != "sqlite":
            try:
                connection.execute(text("SELECT setval(pg_get_serial_sequence('restaurants', 'id'), coalesce(max(id), 1)) FROM restaurants;"))
                connection.execute(text("SELECT setval(pg_get_serial_sequence('menu_items', 'id'), coalesce(max(id), 1)) FROM menu_items;"))
                connection.execute(text("SELECT setval(pg_get_serial_sequence('food_orders', 'id'), coalesce(max(id), 1)) FROM food_orders;"))
                connection.execute(text("SELECT setval(pg_get_serial_sequence('food_reviews', 'id'), coalesce(max(id), 1)) FROM food_reviews;"))
            except Exception as seq_err:
                print(f"Failed to reset postgres sequences: {seq_err}")




# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(users.router,     prefix="/api/users",     tags=["Users & Auth"])
app.include_router(auth.router,      prefix="/api/auth",      tags=["Unified Auth"])
app.include_router(trips.router,     prefix="/api/trips",     tags=["AI Trip Planner"])
app.include_router(fuel.router,      prefix="/api/fuel",      tags=["Fuel & Toll"])
app.include_router(community.router, prefix="/api/community", tags=["Community Routes"])
app.include_router(journal.router,   prefix="/api/journal",   tags=["Trip Journal"])
app.include_router(transport.router, prefix="/api/transport", tags=["Transport"])
app.include_router(provider_router, prefix="/api/provider", tags=["Provider"])
app.include_router(provider_pages_router)
app.include_router(food_provider_pages_router)
app.include_router(booking.router, prefix="/api/booking", tags=["Booking"])
app.include_router(payment.router, prefix="/api/payment", tags=["Payment Gateway"])
app.include_router(food.router, prefix="/api/food", tags=["Food & Restaurant"])
app.include_router(stations.router, prefix="/api/stations", tags=["Fuel Station Availability"])
app.include_router(search.router)
app.include_router(stations.debug_router, prefix="/api", tags=["Debug (DEMO only)"])
app.include_router(fuel_operator_pages.router)   # /fuel-operator/* pages

# UI page routes
app.include_router(auth_pages.router)
app.include_router(dashboard_pages.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "RoadBuddy AI backend is running 🚗", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health_check():
    # Trigger uvicorn reload to pick up new env variables
    return {"status": "ok"}
