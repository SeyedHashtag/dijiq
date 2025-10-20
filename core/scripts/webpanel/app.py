#!/usr/bin/env python3

import sys
import asyncio
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from config import CONFIGS
from middleware import AuthMiddleware
from middleware import AfterRequestMiddleware
from dependency import get_session_manager
from openapi import setup_openapi_schema
from exception_handler import setup_exception_handler

HYSTERIA_CORE_DIR = '/etc/hysteria/core/'
sys.path.append(HYSTERIA_CORE_DIR)

import routers


def create_app() -> FastAPI:
    '''
    Create FastAPI app.
    '''

    app = FastAPI(
        title='Blitz API',
        description='Webpanel for Hysteria2',
        version='0.2.0',
        contact={
            'github': 'https://github.com/ReturnFI/Blitz'
        },
        debug=CONFIGS.DEBUG,
        root_path=f'/{CONFIGS.ROOT_PATH}',
    )

    app.mount('/assets', StaticFiles(directory='assets'), name='assets')

    setup_exception_handler(app)

    app.add_middleware(AuthMiddleware, session_manager=get_session_manager(), api_token=CONFIGS.API_TOKEN)
    app.add_middleware(AfterRequestMiddleware)

    app.include_router(routers.basic.router, prefix='', tags=['Web - Basic'])
    app.include_router(routers.login.router, prefix='', tags=['Web - Authentication'])
    app.include_router(routers.settings.router, prefix='/settings', tags=['Web - Settings'])
    app.include_router(routers.user.router, prefix='/users', tags=['Web - User Management'])
    app.include_router(routers.api.v1.api_v1_router, prefix='/api/v1')

    setup_openapi_schema(app)

    return app


app: FastAPI = create_app()


if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    from hypercorn.middleware import ProxyFixMiddleware

    config = Config()
    config.debug = CONFIGS.DEBUG
    config.bind = ['127.0.0.1:28260']
    config.accesslog = '-'
    config.errorlog = '-'

    app = ProxyFixMiddleware(app, 'legacy')
    asyncio.run(serve(app, config))