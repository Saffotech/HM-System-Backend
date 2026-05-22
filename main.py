from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from Routers import auth
from Routers.roles import router as roles_router  # ← add this
from Models import user, role
from Models import appointments

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hospital Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173", 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(roles_router)  # ← add this

@app.get("/")
def home():
    return {"message": "Hospital api running.."}

from Routers.appointment_router import (
    router as appointments_router
)

app.include_router(appointments_router)