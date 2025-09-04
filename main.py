from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware as Cors
from core.config import settings
import routes.fbref.league.league as leagueRoute
import routes.fbref.players.players as playerRoute
import routes.fbref.mental as mentalRoute

    
# meta
app = FastAPI(
   title=settings.APP_NAME,
    version="0.1.0",
)

app.include_router(leagueRoute.router, prefix="/api/v2")
app.include_router(playerRoute.router, prefix="/api/v2")
app.include_router(mentalRoute.router, prefix="/api/v2")
# root
@app.get("/", tags=["Root"])
async def read_root():
    try:
        return {"message": "Welcome to the Soccer Stats API v2"}
    except Exception as e:
        return {"error": str(e)}

@app.head("/")
async def head_root():
    return Response(status_code=200)



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
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
    
