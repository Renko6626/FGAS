"""Cookie-authenticated SSE adapter for the optional webpage agent prototype."""
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, SecretStr

from backend.application import web_agent
from backend.entrypoints.schemas import Input


class SharedKeyInput(Input):
    api_key: SecretStr


class ChatRequest(BaseModel):
    credential_id: str
    message: str = Field(min_length=1, max_length=8000)
    history: list[dict[str, Any]] = Field(default_factory=list)
    model: str = 'deepseek-flash'
    source: Literal['personal', 'shared'] = 'shared'
    api_key: SecretStr | None = None


def create_router(identity, database_dependency):
    router = APIRouter(prefix='/api/web-agent', tags=['web-agent-prototype'])

    @router.get('/config')
    def config(user=Depends(identity), db=database_dependency):
        return web_agent.configuration(db, user)

    @router.get('/shared-config')
    def shared_config(user=Depends(identity), db=database_dependency):
        return JSONResponse(web_agent.shared_configuration(db, user), headers={'Cache-Control': 'no-store'})

    @router.put('/shared-config')
    def save_shared_config(data: SharedKeyInput, user=Depends(identity), db=database_dependency):
        result = web_agent.save_shared_key(db, user, data.api_key.get_secret_value())
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})

    @router.delete('/shared-config')
    def clear_shared_config(user=Depends(identity), db=database_dependency):
        return JSONResponse(web_agent.clear_shared_key(db, user), headers={'Cache-Control': 'no-store'})

    @router.post('/chat')
    def chat(data: ChatRequest, user=Depends(identity), db=database_dependency):
        access = web_agent.prepare_chat(db, user, data.credential_id, data.model, data.source,
                                       data.api_key.get_secret_value() if data.api_key else '')
        history = web_agent.load_history(data.history)
        return StreamingResponse(web_agent.chat_events(access, data.message, history),
                                 media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @router.get('/balance')
    async def balance(user=Depends(identity), db=database_dependency):
        return await web_agent.shared_balance(db, user)

    return router
