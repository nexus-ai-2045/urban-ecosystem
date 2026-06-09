"""
urban_2d 環境パッケージ。

POI/AOI/Road/AgentProfile/AgentState/VisitRecord/InteractionEvent の
dataclass モデルとデータローダーを提供する。

正本: docs/subagents/contracts/urban-ecosystem-data-contract.md v0.6.4
"""

from .models import (
    POI,
    AOI,
    Road,
    AgentProfile,
    AgentState,
    Activity,
    ActivityPlan,
    VisitRecord,
    InteractionEvent,
)
from .data_loader import (
    load_pois,
    load_aois,
    load_roads,
    load_agent_profiles,
    load_agent_states,
    load_activity_plans,
    load_visit_records,
    load_interaction_events,
    ValidationWarning,
    ValidationError,
)
from .simulation import (
    Simulation,
    load_inputs,
    tick_to_day_time,
)

__all__ = [
    # models
    "POI",
    "AOI",
    "Road",
    "AgentProfile",
    "AgentState",
    "Activity",
    "ActivityPlan",
    "VisitRecord",
    "InteractionEvent",
    # loader
    "load_pois",
    "load_aois",
    "load_roads",
    "load_agent_profiles",
    "load_agent_states",
    "load_activity_plans",
    "load_visit_records",
    "load_interaction_events",
    # simulation
    "Simulation",
    "load_inputs",
    "tick_to_day_time",
    # exceptions
    "ValidationWarning",
    "ValidationError",
]
