from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import require_roles
from app.models import Role, User
from app.schemas.session import SessionStatusOut, StartSessionRequest
from app.services import sessions as session_service

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionStatusOut, status_code=status.HTTP_201_CREATED)
async def start_session(body: StartSessionRequest, _admin: User = Depends(require_roles(Role.ADMINISTRATOR))):
    try:
        await session_service.start_session(body.satellite_id, body.model_id)
    except session_service.SessionAlreadyRunning as exc:
        detail = f"A session is already running for {body.satellite_id}"
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc
    except session_service.NoTrainedChannels as exc:
        detail = f"No trained channels for {body.satellite_id}"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail) from exc
    except session_service.ModelNotRegistered as exc:
        detail = f"Model {body.model_id} is not registered yet (training may still be running)"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return SessionStatusOut(satellite_id=body.satellite_id, model_id=body.model_id, running=True)


@router.delete("/sessions/{satellite_id}")
async def stop_session(satellite_id: str, _admin: User = Depends(require_roles(Role.ADMINISTRATOR))):
    stopped = await session_service.stop_session(satellite_id)
    if not stopped:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No running session for {satellite_id}")
    return {"ok": True}


@router.get("/sessions", response_model=list[SessionStatusOut])
def list_sessions(_user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.EVALUATOR))):
    out = []
    for satellite_id in session_service.list_running():
        c = session_service.counters(satellite_id)
        out.append(
            SessionStatusOut(
                satellite_id=satellite_id,
                model_id="",
                running=True,
                counters=c.__dict__ if c else None,
            )
        )
    # Satellites whose session crashed: not running any more, but still worth showing why.
    running_ids = {row.satellite_id for row in out}
    for satellite_id in session_service.list_errored():
        if satellite_id not in running_ids:
            out.append(
                SessionStatusOut(
                    satellite_id=satellite_id,
                    model_id="",
                    running=False,
                    last_error=session_service.last_error(satellite_id),
                )
            )
    return out
