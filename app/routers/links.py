"""
JSON API for links - useful for scripting, Postman, or a future JS frontend.
The dashboard UI (routers/dashboard.py) covers the same actions via HTML forms.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud
from app.schemas import LinkCreate, LinkOut
from app.routers.auth import require_login

router = APIRouter(prefix="/api/links", tags=["links"])


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


@router.post("", response_model=LinkOut, dependencies=[Depends(require_login)])
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


@router.get("", response_model=list[LinkOut], dependencies=[Depends(require_login)])
def api_list_links(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    links = crud.list_links(db, skip=skip, limit=limit)
    return [_to_link_out(l, db) for l in links]


@router.get("/{link_id}", response_model=LinkOut, dependencies=[Depends(require_login)])
def api_get_link(link_id: int, db: Session = Depends(get_db)):
    link = crud.get_link_by_id(db, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return _to_link_out(link, db)


@router.delete("/{link_id}", dependencies=[Depends(require_login)])
def api_delete_link(link_id: int, db: Session = Depends(get_db)):
    if not crud.delete_link(db, link_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}
