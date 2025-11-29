from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RedditGraphRequest(BaseModel):
    """Incoming request payload for Reddit social graph queries."""

    keyword: str = Field(..., min_length=2, max_length=120)
    time_range: Literal["day", "month", "year"] = "day"
    max_posts: int = Field(50, gt=0, le=50)
    max_comments: int = Field(200, gt=0, le=200)
    max_users: int = Field(50, gt=0, le=50)


class GraphQueryMeta(BaseModel):
    keyword: str
    start_date: datetime
    end_date: datetime
    time_range: str
    post_count: int
    comment_count: int
    user_count: int


class GraphSummary(BaseModel):
    subreddit_counts: Dict[str, int]
    top_users: List[str]


class GraphPost(BaseModel):
    id: str
    title: str
    author: str
    score: int
    num_comments: int
    created_utc: datetime
    permalink: str
    subreddit: str
    url: Optional[str] = None


class GraphComment(BaseModel):
    id: str
    body: str
    author: str
    score: int
    created_utc: datetime
    post_id: str
    parent_id: Optional[str] = None


class GraphUser(BaseModel):
    username: str
    post_count: int
    comment_count: int
    karma: Optional[int] = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    edge_type: Literal["authored", "commented", "thread", "reply"]
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")


class SocialGraphResponse(BaseModel):
    graph_id: Optional[int] = None
    query: GraphQueryMeta
    summary: GraphSummary
    posts: List[GraphPost]
    comments: List[GraphComment]
    users: List[GraphUser]
    edges: List[GraphEdge]


class GraphHistoryItem(BaseModel):
    graph_id: int
    keyword: str
    time_range: str
    created_at: datetime


