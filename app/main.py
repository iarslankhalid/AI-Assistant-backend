from fastapi import FastAPI
from app.api.auth.routes import router as auth_router
from app.api.email.routes import router as email_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(email_router, prefix="/email", tags=["Email"])

@app.get("/ping")
def ping():
    return {"message": "pong"}