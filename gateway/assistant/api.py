from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from .amap import AmapClient
from .models import TurnRequest, TurnResponse
from .providers import ProviderClient, catalog
from .registry import list_connectors
from .secrets import get_secret
from .service import AssistantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http = client
        yield


app = FastAPI(title="Local Assistant Gateway", lifespan=lifespan)


def authenticate(authorization: str | None = Header(default=None)) -> None:
    token = get_secret("device_token")
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_service() -> AssistantService:
    key = get_secret("amap")
    if not key:
        raise HTTPException(status_code=503, detail="Amap key is not configured")
    return AssistantService(AmapClient(key, app.state.http), ProviderClient(app.state.http))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/providers", dependencies=[Depends(authenticate)])
def providers() -> dict:
    return {
        name: {"model": config["model"], "configured": get_secret(name) is not None}
        for name, config in catalog().items()
    }


@app.get("/v1/connectors", dependencies=[Depends(authenticate)])
def connectors() -> dict:
    found = list_connectors()
    return {name: {**metadata, "configured": get_secret(name) is not None} for name, metadata in found.items()}


@app.post("/v1/agent/turns", response_model=TurnResponse, dependencies=[Depends(authenticate)])
async def turn(request: TurnRequest, service: AssistantService = Depends(get_service)) -> TurnResponse:
    return await service.turn(request)
