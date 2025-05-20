import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware as Cors
from routes import fbref_route, AI, team, user, admin, plot, ping
from dotenv import load_dotenv
load_dotenv()

# meta
app = FastAPI(title="Arsenal Overview 25", version="0.1.0")

# routes
app.include_router(fbref_route.router, prefix="/api/v2/team-stats")
app.include_router(AI.router, prefix="/api/v2/ai")
app.include_router(team.router, prefix="/api/v2/team")
app.include_router(user.router, prefix="/api/v2/user")
app.include_router(admin.router, prefix="/admin/optimizer")
app.include_router(plot.router, prefix="/api/v2/test")
app.include_router(ping.router)

# root
@app.get("/", tags=["Root"])
async def read_root():
    try:
        return {"message": "Welcome to the Soccer Stats API v2"}
    except Exception as e:
        return {"error": str(e)}

# cors
# TODO: add DB url. add srver url.
app.add_middleware(
    Cors,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
    
