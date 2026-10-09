"""ORM classes, one per entity in the ER diagram (docs/ER_diagram.docx).

Column names match the ER attributes. Anything beyond the ER diagram is marked
"addition" and explained in docs/ARCHITECTURE.md section 4.1.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, UTCDateTime, utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class Role(StrEnum):
    ANALYST = "Analyst"
    ADMINISTRATOR = "Administrator"
    EVALUATOR = "Evaluator"


class AlertStatus(StrEnum):
    """Alert states from the state transition diagram (Exp 5)."""

    ALERT_RAISED = "AlertRaised"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"


class SeverityLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionOutcome(StrEnum):
    SUPPRESSED = "Suppressed"
    CONFIRMED = "Confirmed"


class Satellite(Base):
    __tablename__ = "satellite"

    satellite_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    norad_id: Mapped[int | None] = mapped_column(Integer)
    # orbital_elements (composite attribute)
    tle_line1: Mapped[str | None] = mapped_column(String(80))
    tle_line2: Mapped[str | None] = mapped_column(String(80))
    current_status: Mapped[str] = mapped_column(String(32), default="Monitored")
    # current_risk_level is derived from open alerts and is not stored.
    # additions
    tle_fetched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    telemetry_source: Mapped[str | None] = mapped_column(String(200))
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)

    mission_tags: Mapped[list["SatelliteMissionTag"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan"
    )
    channels: Mapped[list["Channel"]] = relationship(back_populates="satellite")


class SatelliteMissionTag(Base):
    """SATELLITE.mission_tag is multivalued, so it lives in its own table (1NF)."""

    __tablename__ = "satellite_mission_tag"

    satellite_id: Mapped[str] = mapped_column(ForeignKey("satellite.satellite_id"), primary_key=True)
    mission_tag: Mapped[str] = mapped_column(String(50), primary_key=True)

    satellite: Mapped[Satellite] = relationship(back_populates="mission_tags")


class Channel(Base):
    __tablename__ = "channel"

    channel_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    satellite_id: Mapped[str] = mapped_column(ForeignKey("satellite.satellite_id"), index=True)
    channel_name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(300))
    # additions: link to the SMAP/MSL dataset files
    dataset_chan_id: Mapped[str | None] = mapped_column(String(16))
    spacecraft: Mapped[str | None] = mapped_column(String(8))

    satellite: Mapped[Satellite] = relationship(back_populates="channels")


class TelemetryReading(Base):
    __tablename__ = "telemetry_reading"
    __table_args__ = (Index("ix_reading_channel_time", "channel_id", "timestamp"),)

    reading_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.channel_id"))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    value: Mapped[float] = mapped_column(Float)
    # additions
    split: Mapped[str] = mapped_column(String(8), default="test")
    is_labeled_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)


class DetectionModel(Base):
    __tablename__ = "detection_model"

    model_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100))
    model_type: Mapped[str] = mapped_column(String(50))
    threshold: Mapped[float] = mapped_column(Float)
    trained_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # additions
    artifact_path: Mapped[str | None] = mapped_column(String(300))
    hyperparams: Mapped[dict | None] = mapped_column(JSON)


class Detection(Base):
    __tablename__ = "detection"

    detection_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    satellite_id: Mapped[str] = mapped_column(ForeignKey("satellite.satellite_id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("detection_model.model_id"))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    anomaly_score: Mapped[float] = mapped_column(Float)
    # severity_level is derived from score and persistence; cached because its inputs never change.
    severity_level: Mapped[str | None] = mapped_column(String(16))
    persistence_count: Mapped[int] = mapped_column(Integer, default=0)
    # additions
    window_start: Mapped[int | None] = mapped_column(Integer)
    window_end: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(String(16))

    satellite: Mapped[Satellite] = relationship()
    model: Mapped[DetectionModel] = relationship()
    attributions: Mapped[list["Attribution"]] = relationship(
        back_populates="detection", cascade="all, delete-orphan"
    )
    alert: Mapped["Alert | None"] = relationship(back_populates="detection", uselist=False)

    @property
    def is_anomaly(self) -> bool:
        """Derived: score >= the model's threshold."""
        return self.anomaly_score >= self.model.threshold


class Attribution(Base):
    """Bridge entity resolving the M:N between DETECTION and CHANNEL."""

    __tablename__ = "attribution"

    attribution_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    detection_id: Mapped[str] = mapped_column(ForeignKey("detection.detection_id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channel.channel_id"))
    contribution_score: Mapped[float] = mapped_column(Float)

    detection: Mapped[Detection] = relationship(back_populates="attributions")
    channel: Mapped[Channel] = relationship()


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # name (composite attribute)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(16))
    # addition
    password_hash: Mapped[str] = mapped_column(String(200))

    contact_emails: Mapped[list["UserContactEmail"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserContactEmail(Base):
    """USER.contact_email is multivalued, so it lives in its own table (1NF).

    Any contact email can be used to log in, so each one is unique.
    """

    __tablename__ = "user_contact_email"

    contact_email: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.user_id"), index=True)

    user: Mapped[User] = relationship(back_populates="contact_emails")


class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # A detection raises at most one alert (1:1).
    detection_id: Mapped[str] = mapped_column(ForeignKey("detection.detection_id"), unique=True)
    risk_level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("user.user_id"))
    # additions
    status: Mapped[str] = mapped_column(String(16), default=AlertStatus.ALERT_RAISED)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    detection: Mapped[Detection] = relationship(back_populates="alert")
    acknowledger: Mapped[User | None] = relationship()


class MonitoringConfig(Base):
    __tablename__ = "monitoring_config"

    config_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    satellite_id: Mapped[str] = mapped_column(ForeignKey("satellite.satellite_id"), index=True)
    set_by_user_id: Mapped[str] = mapped_column(ForeignKey("user.user_id"))
    persistence_threshold: Mapped[int] = mapped_column(Integer)
    severity_threshold: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # addition: only the newest row per satellite applies; older rows are history.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    satellite: Mapped[Satellite] = relationship()
    set_by: Mapped[User] = relationship()
