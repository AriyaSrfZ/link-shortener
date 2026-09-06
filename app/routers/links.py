"""
JSON API for links. This is the integration surface for external apps -
everything here is also reachable from the HTML dashboard, but this router
is what you call from code (a mobile app, a WordPress plugin, a script).

Authentication: every route requires either a valid dashboard session
cookie, or an X-API-Key header matching API_KEY in .env. See
app/routers/auth.py for details. If API_KEY is unset in .env, only
session auth works (the API is unusable from outside a browser).

Full parameter and example reference: docs/API.md, or the interactive
docs at /docs (Swagger) and /redoc.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud, analytics
from app.schemas import LinkCreate, LinkOut, ClickOut
from app.routers.auth import require_login

router = APIRouter(prefix="/api/links", tags=["links"])
stats_router = APIRouter(prefix="/api/stats", tags=["stats"])

_UNAUTHORIZED = {
    401: {
        "description": "Missing or invalid credentials",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Login required. Send a valid X-API-Key header, or log in via /login for a session."
                }
            }
        },
    }
}
_NOT_FOUND = {404: {"description": "Link not found", "content": {"application/json": {"example": {"detail": "Link not found"}}}}}


def _to_link_out(link, db: Session) -> LinkOut:
    return LinkOut(
        id=link.id,
        short_code=link.short_code,
        short_url=f"{settings.base_url}/r/{link.short_code}",
        long_url=link.long_url,
        final_url=link.final_url,
        utm_source=link.utm_source,
        utm_medium=link.utm_medium,
        utm_campaign=link.utm_campaign,
        utm_term=link.utm_term,
        utm_content=link.utm_content,
        is_active=link.is_active,
        created_at=link.created_at,
        click_count=crud.count_clicks(db, link.id),
    )


@router.post(
    "",
    response_model=LinkOut,
    dependencies=[Depends(require_login)],
    summary="Create a short link",
    description=(
        "Creates a shortened link with UTM tracking parameters. "
        "utm_source, utm_medium, and utm_campaign are required; "
        "utm_term, utm_content, and custom_code are optional. "
        "Returns 400 if custom_code is already taken or reserved."
    ),
    responses={**_UNAUTHORIZED, 400: {"description": "Invalid input or short code already taken"}},
)
def create_link(payload: LinkCreate, db: Session = Depends(get_db)):
    try:
        link = crud.create_link(
            db,
            long_url=payload.long_url,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_term=payload.utm_term,
            utm_content=payload.utm_content,
            custom_code=payload.custom_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_link_out(link, db)


@router.get(
    "",
    response_model=list[LinkOut],
    dependencies=[Depends(require_login)],
    summary="List all links",
    description="Returns links newest-first. Use skip/limit to paginate.",
    responses=_UNAUTHORIZED,
)
def api_list_links(
    skip: int = Query(0, ge=0, description="Number of links to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=500, description="Max number of links to return (1-500)."),
    db: Session = Depends(get_db),
):
    links = crud.list_links(db, skip=skip, limit=limit)
    return [_to_link_out(l, db) for l in links]


@router.get(
    "/{link_id}",
    response_model=LinkOut,
    dependencies=[Depends(require_login)],
    summary="Get one link",
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
def api_get_link(link_id: int, db: Session = Depends(get_db)):
    link = crud.get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return _to_link_out(link, db)


@router.delete(
    "/{link_id}",
    dependencies=[Depends(require_login)],
    summary="Delete a link",
    description="Permanently deletes the link and all of its click history. This cannot be undone.",
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
def api_delete_link(link_id: int, db: Session = Depends(get_db)):
    if not crud.delete_link(db, link_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get(
    "/{link_id}/clicks",
    response_model=list[ClickOut],
    dependencies=[Depends(require_login)],
    summary="Get click log for a link",
    description="Returns individual click records, newest first, with device/browser/country backtrace data.",
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
def api_get_link_clicks(
    link_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    link = crud.get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    clicks = sorted(link.clicks, key=lambda c: c.clicked_at, reverse=True)
    return clicks[skip: skip + limit]


@router.get(
    "/{link_id}/stats",
    dependencies=[Depends(require_login)],
    summary="Get aggregate analytics for a link",
    description=(
        "Returns click totals, a daily click count series, top referrers, "
        "device breakdown, and top countries for a single link. "
        "Use the site-wide equivalent at GET /api/stats for all links combined."
    ),
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
def api_get_link_stats(
    link_id: int,
    days: int = Query(14, ge=1, le=90, description="Number of days to include in the daily series."),
    db: Session = Depends(get_db),
):
    link = crud.get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return {
        "summary": analytics.total_clicks_summary(db, link_id=link_id),
        "daily": analytics.clicks_per_day(db, link_id=link_id, days=days),
        "top_referrers": analytics.top_referrers(db, link_id=link_id),
        "devices": analytics.device_breakdown(db, link_id=link_id),
        "top_countries": analytics.top_countries(db, link_id=link_id),
    }


@stats_router.get(
    "",
    dependencies=[Depends(require_login)],
    summary="Get site-wide aggregate analytics",
    description="Same shape as GET /api/links/{id}/stats, but combined across every link.",
    responses=_UNAUTHORIZED,
)
def api_get_site_stats(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return {
        "summary": analytics.total_clicks_summary(db),
        "daily": analytics.clicks_per_day(db, days=days),
        "top_referrers": analytics.top_referrers(db),
        "devices": analytics.device_breakdown(db),
        "top_countries": analytics.top_countries(db),
    }
