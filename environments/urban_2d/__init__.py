"""
urban_2d 環境パッケージ。

POI/AOI/Road/AgentProfile/AgentState/VisitRecord/InteractionEvent の
dataclass モデルとデータローダーを提供する。

正本: docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0
"""

from .models import (
    POI,
    AOI,
    Road,
    AgentProfile,
    AgentState,
    VisitRecord,
    InteractionEvent,
)
from .data_loader import (
    load_pois,
    load_aois,
    load_roads,
    load_agent_profiles,
    load_agent_states,
    load_visit_records,
    load_interaction_events,
    ValidationWarning,
    ValidationError,
)

__all__ = [
    # models
    "POI",
    "AOI",
    "Road",
    "AgentProfile",
    "AgentState",
    "VisitRecord",
    "InteractionEvent",
    # loader
    "load_pois",
    "load_aois",
    "load_roads",
    "load_agent_profiles",
    "load_agent_states",
    "load_visit_records",
    "load_interaction_events",
    # exceptions
    "ValidationWarning",
    "ValidationError",
]
