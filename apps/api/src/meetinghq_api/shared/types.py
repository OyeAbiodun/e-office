"""Shared strongly typed identifiers."""

import uuid
from typing import NewType

OrganizationId = NewType("OrganizationId", uuid.UUID)
WorkspaceId = NewType("WorkspaceId", uuid.UUID)
TeamId = NewType("TeamId", uuid.UUID)
UserId = NewType("UserId", uuid.UUID)
