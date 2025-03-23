from fastapi import FastAPI
from app.api.auth.routes import router as auth_router
from app.api.outlook.routes import router as outlook_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(outlook_router, prefix="/email", tags=["Email"])

