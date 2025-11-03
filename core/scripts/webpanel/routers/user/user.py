from fastapi import APIRouter, HTTPException, Request, Depends, Query, Path, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND
import math

from dependency import get_templates
from .viewmodel import User
import cli_api


router = APIRouter()


async def get_users_page(
    request: Request,
    templates: Jinja2Templates,
    page: int,
    limit: int
):
    try:
        users_list = cli_api.list_users() or []
        total_users = len(users_list)
        total_pages = math.ceil(total_users / limit) if limit > 0 else 1

        if page > total_pages and total_pages > 0:
            return RedirectResponse(url=f"/users/{total_pages}", status_code=HTTP_302_FOUND)
        if page < 1:
            return RedirectResponse(url=f"/users/1", status_code=HTTP_302_FOUND)

        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_list = users_list[start_index:end_index]

        users: list[User] = [User.from_dict(user_data.get('username', ''), user_data) for user_data in paginated_list]

        return templates.TemplateResponse(
            'users.html',
            {
                'users': users,
                'request': request,
                'current_page': page,
                'total_pages': total_pages,
                'limit': limit,
                'total_users': total_users,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.get('/{page}', name="users_paginated")
async def users_paginated(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
    page: int = Path(..., ge=1),
    limit: int = Cookie(default=50, ge=1)
):
    return await get_users_page(request, templates, page, limit)


@router.get('/', name="users")
async def users_root(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
    limit: int = Cookie(default=50, ge=1)
):
    return await get_users_page(request, templates, 1, limit)