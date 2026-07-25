from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.schemas.schemas import UserCreate, UserOut, UserUpdate, PasswordChange, TokenOut, VehicleCreate, VehicleOut, OtpVerify
from sqlalchemy.exc import IntegrityError
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.core.database import get_db
from app.core.email_otp import generate_and_send_otp, verify_otp, clear_otp, _otp_store
from app.models.models import User, Vehicle

router = APIRouter()


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Start registration: send OTP, stash pending user until verified."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        generate_and_send_otp(data.email, data.name)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    _otp_store[data.email]["name"] = data.name
    _otp_store[data.email]["password"] = hash_password(data.password)

    return {"message": "OTP sent", "email": data.email}


@router.post("/verify-otp", response_model=UserOut, status_code=201)
def verify_otp_endpoint(data: OtpVerify, db: Session = Depends(get_db)):
    """Verify OTP and create the actual user account."""
    record = _otp_store.get(data.email)
    if not record or not verify_otp(data.email, data.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = User(
        name=record["name"],
        email=data.email,
        password_hash=record["password"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    clear_otp(data.email)

    return UserOut(
        id=str(user.id),
        name=user.name,
        email=user.email,
        home_city=None,
        total_trips=0,
    )


@router.post("/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Log in and get a JWT access token."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token)


from pydantic import BaseModel, EmailStr, Field

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResetRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Initiate password reset: send OTP to verified email."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="No account registered with this email address.")
    try:
        generate_and_send_otp(data.email, user.name)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"message": "OTP sent", "email": data.email}

@router.post("/forgot-password/reset")
def forgot_password_reset(data: ForgotPasswordResetRequest, db: Session = Depends(get_db)):
    """Verify OTP and update user's password."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="No account registered with this email address.")
    
    if not verify_otp(data.email, data.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")
        
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password reset successful"}


# ── Profile ───────────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserOut)
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the logged-in user's profile."""
    user = db.query(User).filter(
        User.id == int(current_user["user_id"])
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(
        id          = str(user.id),
        name        = user.name,
        email       = user.email,
        home_city   = None,
        total_trips = len(user.trips),
    )


@router.get("/preferences")
def get_preferences(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get or compute travel preference snapshot for logged-in user."""
    from app.models.models import UserPreference
    from app.services.preference_engine import compute_user_preferences

    user_id = int(current_user["user_id"])
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        pref = compute_user_preferences(db, user_id)

    if not pref:
        return {
            "has_preferences": False,
            "preferred_budget_tier": None,
            "preferred_travel_mode": None,
            "avoid_tolls_default": False,
            "avoid_highways_default": False,
        }

    return {
        "has_preferences": True,
        "preferred_budget_tier": pref.preferred_budget_tier,
        "preferred_travel_mode": pref.preferred_travel_mode,
        "avoid_tolls_default": pref.avoid_tolls_default,
        "avoid_highways_default": pref.avoid_highways_default,
        "preferred_accommodation": pref.preferred_accommodation,
        "last_computed_at": pref.last_computed_at.isoformat() if pref.last_computed_at else None,
    }




@router.patch("/me", response_model=UserOut)
def update_profile(
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the logged-in user's name and/or email."""
    user = db.query(User).filter(
        User.id == int(current_user["user_id"])
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
 
    if data.name is not None:
        user.name = data.name
 
    if data.email is not None and data.email != user.email:
        existing = db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="That email is already in use")
        user.email = data.email
 
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="That email is already in use")
 
    db.refresh(user)
 
    return UserOut(
        id          = str(user.id),
        name        = user.name,
        email       = user.email,
        home_city   = None,
        total_trips = len(user.trips),
    )
    
@router.post("/change-password", status_code=204)
def change_password(
    data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the logged-in user's password after verifying the current one."""
    user = db.query(User).filter(
        User.id == int(current_user["user_id"])
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return None


# ── Vehicles ──────────────────────────────────────────────────────────────────

@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def add_vehicle(
    data: VehicleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a vehicle to the user's garage."""
    vehicle = Vehicle(
        user_id      = int(current_user["user_id"]),
        name         = data.name,
        fuel_type    = data.fuel_type,
        category     = data.category,
        mileage_kmpl = data.mileage_kmpl,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return VehicleOut(
        id           = str(vehicle.id),
        user_id      = str(vehicle.user_id),
        name         = vehicle.name,
        fuel_type    = vehicle.fuel_type,
        category     = vehicle.category,
        mileage_kmpl = vehicle.mileage_kmpl,
    )


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all vehicles for the logged-in user."""
    vehicles = db.query(Vehicle).filter(
        Vehicle.user_id == int(current_user["user_id"])
    ).all()

    return [
        VehicleOut(
            id           = str(v.id),
            user_id      = str(v.user_id),
            name         = v.name,
            fuel_type    = v.fuel_type,
            category     = v.category,
            mileage_kmpl = v.mileage_kmpl,
        )
        for v in vehicles
    ]


@router.delete("/vehicles/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a vehicle from the user's garage."""
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == int(vehicle_id),
        Vehicle.user_id == int(current_user["user_id"])
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    db.delete(vehicle)
    db.commit()
    return None