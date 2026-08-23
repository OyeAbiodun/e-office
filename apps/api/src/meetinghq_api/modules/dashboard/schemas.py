"""Widget-based dashboard contracts."""

from datetime import datetime

from pydantic import BaseModel


class MetricWidget(BaseModel):
    """Independently renderable metric."""

    id: str
    label: str
    value: int | str


class ActivityItem(BaseModel):
    """Recent activity timeline item."""

    id: str
    event_type: str
    subject_type: str
    occurred_at: datetime
    payload: dict[str, object]


class DashboardResponse(BaseModel):
    """Dashboard widget payload."""

    organization_name: str
    widgets: list[MetricWidget]
    recent_activity: list[ActivityItem]
    quick_actions: list[str]
