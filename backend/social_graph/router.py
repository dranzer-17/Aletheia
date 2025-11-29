from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from auth.router import get_current_user
from database import db, get_next_sequence
from .reddit_service import fetch_reddit_graph
from .schema import GraphHistoryItem, RedditGraphRequest, SocialGraphResponse

router = APIRouter(prefix="/social-graph", tags=["Social Graph"])


@router.post("/reddit", response_model=SocialGraphResponse)
async def reddit_social_graph(
    payload: RedditGraphRequest, current_user: dict = Depends(get_current_user)
) -> SocialGraphResponse:
    try:
        response = await fetch_reddit_graph(payload)
        graph_id = await get_next_sequence("graphs")
        await db["graphs"].insert_one(
            {
                "graph_id": graph_id,
                "user_id": current_user["user_id"],
                "keyword": payload.keyword,
                "time_range": payload.time_range,
                "created_at": datetime.now(timezone.utc),
                "response": response.model_dump(),
            }
        )
        response.graph_id = graph_id
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail="Failed to build Reddit graph") from exc


@router.get("/graphs", response_model=List[GraphHistoryItem])
async def list_graphs(current_user: dict = Depends(get_current_user)) -> List[GraphHistoryItem]:
    cursor = (
        db["graphs"]
        .find(
            {"user_id": current_user["user_id"]},
            {"_id": 0, "graph_id": 1, "keyword": 1, "time_range": 1, "created_at": 1},
        )
        .sort("created_at", -1)
    )
    docs = await cursor.to_list(length=50)
    return [GraphHistoryItem(**doc) for doc in docs]


@router.get("/graphs/{graph_id}", response_model=SocialGraphResponse)
async def get_graph(graph_id: int, current_user: dict = Depends(get_current_user)) -> SocialGraphResponse:
    doc = await db["graphs"].find_one(
        {"graph_id": graph_id, "user_id": current_user["user_id"]}, {"_id": 0, "response": 1, "graph_id": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Graph not found")

    response = SocialGraphResponse(**doc["response"])
    response.graph_id = doc["graph_id"]
    return response


