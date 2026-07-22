from __future__ import annotations

from starlette.routing import Mount

from ashare_f10.api.app import app
from ashare_f10.api.raw_pack import router as raw_pack_router
from ashare_f10.api.research_pack import router as research_pack_router

# The existing SPA is mounted at "/" as the final route. Insert API routes before
# that catch-all mount without changing the stable base app used by older tests.
static_mounts = [
    route for route in app.router.routes if isinstance(route, Mount) and route.path in {"", "/"}
]
for route in static_mounts:
    app.router.routes.remove(route)
app.include_router(raw_pack_router)
app.include_router(research_pack_router)
app.router.routes.extend(static_mounts)
app.version = "0.6.0"
