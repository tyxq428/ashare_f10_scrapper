from __future__ import annotations

from ashare_f10.api import visual_execution_v2 as implementation
from ashare_f10.api.visual_jobs_runtime import VisualJobManager
from ashare_f10.config import settings

# Endpoint functions in visual_execution_v2 resolve their module-level manager at
# request time. Replace it here so the stable canonical router uses the production
# runtime manager without duplicating the API definitions.
implementation.manager = VisualJobManager(settings)

VisualJobRequest = implementation.VisualJobRequest
manager = implementation.manager
router = implementation.router
visual_capabilities = implementation.visual_capabilities

__all__ = ["VisualJobRequest", "manager", "router", "visual_capabilities"]
