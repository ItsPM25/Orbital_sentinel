from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User
from app.pipeline.explain.ranking import rank_satellites
from app.schemas.ranking import SatelliteRankingOut

router = APIRouter(tags=["ranking"])


@router.get("/ranking", response_model=list[SatelliteRankingOut])
def get_ranking(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """REQ-10: satellites ordered by current severity, then risk_level, then recency."""
    return [SatelliteRankingOut.from_ranking(row) for row in rank_satellites(db)]
