from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import notes, analytics

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://research-project-delta-gold.vercel.app" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],    
    allow_headers=["*"],    
)


app.include_router(notes.router)
app.include_router(analytics.router)

@app.get("/")
async def root():
    return {"message": "Trust Research API is running modularly!"}
