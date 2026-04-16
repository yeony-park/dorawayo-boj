from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.templating import Jinja2Templates

from boj_backup.db import get_problem_list, get_problem_detail

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dorawayo-boj")
@router.get("/dorawayo-boj/")
def probelm_list(
    request: Request,
    q: str = "",
    tier: str = "",
    tag: str = "",
    page: int = Query(1, ge=1),
):
    data = get_problem_list(
        query=q.strip(),
        tier=tier.strip(),
        tag=tag.strip(),
        page=page,
    )

    return templates.TemplateResponse(
        "boj/list.html",
        {
            "request": request,
            "problems": data["problems"],
            "total_count": data["total_count"],
            "page": data["page"],
            "page_size": data["page_size"],
            "total_pages": data["total_pages"],
            "query": q,
            "tier": tier,
            "tag": tag,
            "tier_groups": ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ruby", "Unrated"],
        },
    )

@router.get("/dorawayo-boj/{problem_id}")
def problem_detail(request: Request, problem_id: int):
    problem = get_problem_detail(problem_id)

    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    
    return templates.TemplateResponse(
        "boj/detail.html",
        {
            "request": request,
            "problem": problem,
        },
    )