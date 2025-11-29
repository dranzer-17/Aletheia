from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from database import db, get_next_sequence
from auth.schemas import UserCreate, Token, UserResponse
from auth.security import get_password_hash, verify_password, create_access_token
from config import SECRET_KEY, ALGORITHM
from logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Dependency setup for protecting routes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token validation failed: Missing email in payload")
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        raise credentials_exception
    
    user = await db["users"].find_one({"email": email})
    if user is None:
        logger.warning(f"Token validation failed: User not found - {email}")
        raise credentials_exception
    return user

# --- ROUTES ---

@router.post("/signup", response_model=Token)
async def signup(user: UserCreate):
    logger.info(f"Signup attempt for email: {user.email}")
    # Check if user already exists
    if await db["users"].find_one({"email": user.email}):
        logger.warning(f"Signup failed: Email already registered - {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password length
    if len(user.password) > 72:
        logger.warning(f"Signup failed: Password too long for email - {user.email}")
        raise HTTPException(
            status_code=400, 
            detail="Password is too long (maximum 72 characters)"
        )
    
    # Hash password and save
    try:
        user_dict = user.model_dump()
        user_dict["user_id"] = await get_next_sequence("users")
        user_dict["hashed_password"] = get_password_hash(user.password)
        del user_dict["password"]
        
        await db["users"].insert_one(user_dict)
        logger.info(f"User successfully signed up: {user.email} (user_id: {user_dict['user_id']})")
        
        # Auto-login (Generate Token)
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except ValueError as e:
        logger.error(f"Signup error for {user.email}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    logger.info(f"Login attempt for email: {form_data.username}")
    # OAuth2PasswordRequestForm expects 'username' and 'password'
    user = await db["users"].find_one({"email": form_data.username})
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        logger.warning(f"Login failed: Invalid credentials for email - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"User successfully logged in: {form_data.username}")
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user