from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import notes, analytics

app = FastAPI(title="Trust Research Annotation API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# 注册路由模块
app.include_router(notes.router)
app.include_router(analytics.router)

@app.get("/")
async def root():
    return {"message": "Trust Research API is running modularly!"}
