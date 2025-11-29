from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Sequence, Set, Tuple

import praw
from praw.models import Comment as PrawComment, Submission
from prawcore.exceptions import PrawcoreException

from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

from logger import get_logger

from .schema import (
    GraphComment,
    GraphEdge,
    GraphPost,
    GraphQueryMeta,
    GraphSummary,
    GraphUser,
    RedditGraphRequest,
    SocialGraphResponse,
)

logger = get_logger(__name__)

if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT):
    raise RuntimeError("Reddit API credentials are not configured")

reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)

TIME_RANGE_TO_DAYS = {"day": 1, "month": 30, "year": 365}
TIME_RANGE_TO_PRAW = {"day": "day", "month": "month", "year": "year"}
MAX_REDDIT_POSTS = 20
COMMENTS_PER_POST = 5
MAX_SEARCH_BATCH = 200


def _to_datetime(timestamp: int | float | None) -> datetime:
    if not timestamp:
        return datetime.now(tz=UTC)
    return datetime.fromtimestamp(float(timestamp), tz=UTC)


def _normalize_author(author: str | None) -> str:
    value = (author or "").strip() or "[deleted]"
    return value[:80]


def _build_permalink(submission: Submission) -> str:
    return f"https://www.reddit.com{submission.permalink}"


def _matches_keyword(submission: Submission, normalized_keyword: str) -> bool:
    title = (submission.title or "").lower()
    body = (submission.selftext or "").lower()
    return normalized_keyword in title or normalized_keyword in body


def _collect_posts(
    keyword: str, max_posts: int, time_range: str
) -> Tuple[List[GraphPost], List[Submission]]:
    submissions: List[Submission] = []
    posts: List[GraphPost] = []

    target_posts = min(max_posts, MAX_REDDIT_POSTS)
    normalized_keyword = keyword.lower()

    search_iter = reddit.subreddit("all").search(
        query=keyword,
        sort="top",
        time_filter=TIME_RANGE_TO_PRAW[time_range],
        limit=target_posts * 6,
    )

    attempts = 0
    for submission in search_iter:
        attempts += 1
        if attempts > MAX_SEARCH_BATCH:
            break
        if len(posts) >= target_posts:
            break
        if not _matches_keyword(submission, normalized_keyword):
            continue
        submissions.append(submission)
        posts.append(
            GraphPost(
                id=submission.id,
                title=(submission.title or "Untitled post")[:280],
                author=_normalize_author(getattr(submission.author, "name", None)),
                score=int(submission.score or 0),
                num_comments=int(submission.num_comments or 0),
                created_utc=_to_datetime(submission.created_utc),
                permalink=_build_permalink(submission),
                subreddit=submission.subreddit.display_name.lower(),
                url=submission.url,
            )
        )

    return posts, submissions


def _collect_comments(
    submissions: Sequence[Submission], per_post_limit: int
) -> List[GraphComment]:
    collected: List[GraphComment] = []
    seen_ids: Set[str] = set()

    for submission in submissions:
        try:
            submission.comment_sort = "top"
            submission.comments.replace_more(limit=0)
        except PrawcoreException as exc:
            logger.warning("Failed to load comments for %s: %s", submission.id, exc)
            continue

        per_post_count = 0
        for comment in submission.comments.list():
            if not isinstance(comment, PrawComment):
                continue
            if comment.id in seen_ids:
                continue
            if per_post_count >= per_post_limit:
                break
            seen_ids.add(comment.id)
            collected.append(
                GraphComment(
                    id=comment.id,
                    body=(comment.body or "").strip()[:500],
                    author=_normalize_author(getattr(comment.author, "name", None)),
                    score=int(comment.score or 0),
                    created_utc=_to_datetime(comment.created_utc),
                    post_id=comment.link_id.replace("t3_", ""),
                    parent_id=comment.parent_id,
                )
            )
            per_post_count += 1

    return collected


def _build_users(
    posts: Sequence[GraphPost],
    comments: Sequence[GraphComment],
    max_users: int,
) -> tuple[List[GraphUser], Set[str]]:
    user_map: Dict[str, Dict[str, Set[str]]] = defaultdict(
        lambda: {"posts": set(), "comments": set()}
    )

    for post in posts:
        user_map[post.author]["posts"].add(post.id)
    for comment in comments:
        user_map[comment.author]["comments"].add(comment.id)

    ranked_users = sorted(
        user_map.items(),
        key=lambda item: (len(item[1]["posts"]) * 2 + len(item[1]["comments"])),
        reverse=True,
    )

    selected_users = ranked_users[:max_users]
    allowed_usernames = {username for username, _ in selected_users}
    users = [
        GraphUser(
            username=username,
            post_count=len(info["posts"]),
            comment_count=len(info["comments"]),
        )
        for username, info in selected_users
    ]
    return users, allowed_usernames


def _build_edges(
    posts: Sequence[GraphPost],
    comments: Sequence[GraphComment],
    allowed_users: Set[str],
) -> List[GraphEdge]:
    edges: Dict[str, GraphEdge] = {}

    def add_edge(edge_id: str, edge_type: str, from_node: str, to_node: str) -> None:
        if edge_id in edges:
            return
        edges[edge_id] = GraphEdge(
            id=edge_id,
            edge_type=edge_type,  # type: ignore[arg-type]
            from_node=from_node,
            to_node=to_node,
        )

    for post in posts:
        if post.author in allowed_users:
            add_edge(
                f"authored:{post.author}->{post.id}",
                "authored",
                f"user:{post.author}",
                f"post:{post.id}",
            )

    for comment in comments:
        comment_node = f"comment:{comment.id}"
        post_node = f"post:{comment.post_id}"
        add_edge(
            f"thread:{comment.id}->{comment.post_id}",
            "thread",
            comment_node,
            post_node,
        )

        if comment.author in allowed_users:
            add_edge(
                f"commented:{comment.author}->{comment.id}",
                "commented",
                f"user:{comment.author}",
                comment_node,
            )

        parent_id = comment.parent_id or ""
        if parent_id.startswith("t1_"):
            parent_comment = parent_id.replace("t1_", "")
            add_edge(
                f"reply:{comment.id}->{parent_comment}",
                "reply",
                comment_node,
                f"comment:{parent_comment}",
            )

    return list(edges.values())


async def fetch_reddit_graph(payload: RedditGraphRequest) -> SocialGraphResponse:
    keyword = payload.keyword.strip()
    if not keyword:
        raise ValueError("Keyword is required")

    time_range = payload.time_range
    if time_range not in TIME_RANGE_TO_DAYS:
        raise ValueError("Unsupported time range")

    end_dt = datetime.now(tz=UTC)
    start_dt = end_dt - timedelta(days=TIME_RANGE_TO_DAYS[time_range])

    try:
        posts, submissions = await asyncio.to_thread(
            _collect_posts, keyword, payload.max_posts, time_range
        )
    except PrawcoreException as exc:
        logger.error("Reddit API error: %s", exc)
        raise ValueError("Unable to query Reddit at the moment. Please try again.") from exc

    if not posts:
        logger.info("No Reddit posts found for keyword '%s'", keyword)
        query_meta = GraphQueryMeta(
            keyword=keyword,
            start_date=start_dt,
            end_date=end_dt,
            time_range=time_range,
            post_count=0,
            comment_count=0,
            user_count=0,
        )
        empty_summary = GraphSummary(subreddit_counts={}, top_users=[])
        return SocialGraphResponse(
            query=query_meta,
            summary=empty_summary,
            posts=[],
            comments=[],
            users=[],
            edges=[],
        )

    comments = await asyncio.to_thread(
        _collect_comments, submissions, COMMENTS_PER_POST
    )

    users, allowed_usernames = _build_users(posts, comments, payload.max_users)
    edges = _build_edges(posts, comments, allowed_usernames)

    subreddit_counts = dict(Counter(post.subreddit for post in posts))
    top_users = [user.username for user in users[:5]]

    summary = GraphSummary(subreddit_counts=subreddit_counts, top_users=top_users)
    query_meta = GraphQueryMeta(
        keyword=keyword,
        start_date=start_dt,
        end_date=end_dt,
        time_range=time_range,
        post_count=len(posts),
        comment_count=len(comments),
        user_count=len(users),
    )

    logger.info(
        "Reddit graph built for '%s': %s posts, %s comments, %s users",
        keyword,
        len(posts),
        len(comments),
        len(users),
    )

    return SocialGraphResponse(
        query=query_meta,
        summary=summary,
        posts=posts,
        comments=comments,
        users=users,
        edges=edges,
    )


