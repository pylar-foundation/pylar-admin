"""The AdminSite — user-facing entry point for model registration and route setup."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pylar_admin.config import AdminConfig, ModelAdmin
from pylar_admin.registry import AdminRegistry
from pylar.database.model import Model
from pylar.http.middleware import Middleware
from pylar.http.request import Request
from pylar.http.response import Response
from pylar.routing.router import Router


#: Path to the built Vue.js SPA assets bundled with the package.
_SPA_DIST = Path(__file__).parent / "spa" / "dist"


class AdminSite:
    """Main admin object that users interact with.

    Wraps the registry and provides ``register()`` for convenience.
    The ``urls()`` method mounts all admin routes (API + SPA shell) on
    the application router.

    Usage in a service provider::

        site = container.make(AdminSite)
        site.register(User)
        site.register(Post, PostAdmin())
    """

    def __init__(self, config: AdminConfig, registry: AdminRegistry) -> None:
        self._config = config
        self._registry = registry

    @property
    def config(self) -> AdminConfig:
        return self._config

    @property
    def registry(self) -> AdminRegistry:
        return self._registry

    def register(
        self,
        model: type[Model],
        config: ModelAdmin | None = None,
    ) -> None:
        """Register a model for admin access."""
        self._registry.register(model, config)

    def urls(
        self,
        router: Router,
        *,
        middleware: Sequence[type[Middleware]] = (),
    ) -> None:
        """Mount admin API and SPA routes on *router*.

        Creates a route group under ``config.prefix`` with the given
        middleware stack.  All routes are self-contained — no changes
        required outside this module.
        """
        from pylar_admin.controllers.api import AdminApiController
        from pylar_admin.controllers.auth import AdminAuthController

        prefix = self._config.prefix.rstrip("/")

        # ---- Public auth routes (no RequireAuthMiddleware) ----
        # These need DatabaseSessionMiddleware + SessionMiddleware + AuthMiddleware
        # but NOT RequireAuthMiddleware — so we build a separate group.
        public_mw = [m for m in middleware if "RequireAuth" not in m.__name__]
        public = router.group(prefix=prefix, middleware=tuple(public_mw))
        public.post("/api/login", AdminAuthController.login, name="admin.login")
        public.post("/api/logout", AdminAuthController.logout, name="admin.logout")
        public.get("/api/user", AdminAuthController.user, name="admin.user")
        # WebAuthn / passkey login — graceful 404 when pylar[webauthn]
        # is not configured, so the button can be hidden from the SPA
        # at first paint instead of failing on click.
        public.get(
            "/api/login/webauthn/options",
            AdminAuthController.webauthn_options,
            name="admin.login.webauthn.options",
        )
        public.post(
            "/api/login/webauthn/verify",
            AdminAuthController.webauthn_verify,
            name="admin.login.webauthn.verify",
        )

        # ---- Protected JSON API routes ----
        group = router.group(prefix=prefix, middleware=tuple(middleware))

        group.get("/api/dashboard", AdminApiController.dashboard, name="admin.dashboard")
        group.get("/api/menu", AdminApiController.menu, name="admin.menu")
        group.get(
            "/api/system/schedule",
            AdminApiController.schedule_list,
            name="admin.system.schedule",
        )
        # ---- System → Queues (Horizon-style monitor) ----
        from pylar_admin.controllers.queues import QueueController

        group.get(
            "/api/system/queues",
            QueueController.index,
            name="admin.system.queues",
        )
        group.get(
            "/api/system/queues/failed",
            QueueController.failed_list,
            name="admin.system.queues.failed",
        )
        group.post(
            "/api/system/queues/failed/retry",
            QueueController.retry_failed,
            name="admin.system.queues.failed.retry",
        )
        group.delete(
            "/api/system/queues/failed",
            QueueController.flush_failed,
            name="admin.system.queues.failed.flush",
        )
        group.delete(
            "/api/system/queues/failed/{id}",
            QueueController.forget_failed,
            name="admin.system.queues.failed.forget",
        )
        group.get(
            "/api/system/queues/{queue_name}/pending",
            QueueController.pending_list,
            name="admin.system.queues.pending",
        )
        group.get(
            "/api/system/queues/{queue_name}/recent",
            QueueController.recent_list,
            name="admin.system.queues.recent",
        )
        group.get(
            "/api/system/queues/{queue_name}/jobs/{id}",
            QueueController.job_detail,
            name="admin.system.queues.job",
        )
        group.delete(
            "/api/system/queues/{queue_name}/pending/{id}",
            QueueController.cancel_pending,
            name="admin.system.queues.cancel",
        )
        group.post(
            "/api/system/queues/{queue_name}/purge",
            QueueController.purge_pending,
            name="admin.system.queues.purge",
        )

        # ---- Self-service profile + passkey management ----
        from pylar_admin.controllers.profile import ProfileController

        group.get(
            "/api/profile",
            ProfileController.index,
            name="admin.profile",
        )
        group.get(
            "/api/profile/webauthn/register/options",
            ProfileController.register_options,
            name="admin.profile.webauthn.register.options",
        )
        group.post(
            "/api/profile/webauthn/register/verify",
            ProfileController.register_verify,
            name="admin.profile.webauthn.register.verify",
        )
        group.patch(
            "/api/profile/webauthn/{id}",
            ProfileController.rename,
            name="admin.profile.webauthn.rename",
        )
        group.delete(
            "/api/profile/webauthn/{id}",
            ProfileController.revoke,
            name="admin.profile.webauthn.revoke",
        )

        # ---- System → WebAuthn credentials (ADR-0013 phase 15c) ----
        from pylar_admin.controllers.webauthn import WebauthnController

        group.get(
            "/api/system/webauthn",
            WebauthnController.index,
            name="admin.system.webauthn",
        )
        group.delete(
            "/api/system/webauthn/{id}",
            WebauthnController.revoke,
            name="admin.system.webauthn.revoke",
        )
        group.patch(
            "/api/system/webauthn/{id}",
            WebauthnController.update,
            name="admin.system.webauthn.update",
        )
        group.get("/api/models", AdminApiController.models_index, name="admin.models")
        group.get(
            "/api/models/{slug}/schema",
            AdminApiController.model_schema,
            name="admin.model_schema",
        )
        group.get(
            "/api/models/{slug}/records",
            AdminApiController.records_index,
            name="admin.records.index",
        )
        group.post(
            "/api/models/{slug}/records",
            AdminApiController.record_create,
            name="admin.records.store",
        )
        group.get(
            "/api/models/{slug}/records/{pk}",
            AdminApiController.record_show,
            name="admin.records.show",
        )
        group.put(
            "/api/models/{slug}/records/{pk}",
            AdminApiController.record_update,
            name="admin.records.update",
        )
        group.delete(
            "/api/models/{slug}/records/{pk}",
            AdminApiController.record_delete,
            name="admin.records.destroy",
        )

        # ---- Bulk actions (phase 12) ----
        group.get(
            "/api/models/{slug}/actions",
            AdminApiController.actions_index,
            name="admin.actions.index",
        )
        group.post(
            "/api/models/{slug}/actions/{name}",
            AdminApiController.run_action,
            name="admin.actions.run",
        )

        # ---- SPA shell + static assets (public — Vue handles auth) ----
        public.get("/assets/{path:path}", _serve_spa_asset, name="admin.assets")
        # Catch-all: serve index.html for all non-API admin paths so the
        # Vue router can handle client-side navigation.
        public.get("/{path:path}", _serve_spa_shell, name="admin.spa")
        public.get("", _serve_spa_shell, name="admin.spa.root")


async def _serve_spa_shell(request: Request, path: str = "") -> Response:
    """Serve the Vue.js SPA index.html for all non-API admin paths."""
    from pylar.http import HtmlResponse

    index = _SPA_DIST / "index.html"
    if not index.exists():
        return HtmlResponse(
            _FALLBACK_HTML,
            status_code=200,
        )
    return HtmlResponse(index.read_text(encoding="utf-8"))


async def _serve_spa_asset(request: Request, path: str = "") -> Response:
    """Serve static assets (JS, CSS, fonts) from the SPA dist directory."""
    file_path = (_SPA_DIST / path).resolve()
    # Path traversal guard.
    if not str(file_path).startswith(str(_SPA_DIST.resolve())):
        return Response(status_code=403)

    if not file_path.exists() or not file_path.is_file():
        return Response(status_code=404)

    content_type = _guess_content_type(file_path.suffix)
    content = file_path.read_bytes()
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def _guess_content_type(suffix: str) -> str:
    """Map file suffix to MIME type."""
    types: dict[str, str] = {
        ".js": "application/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".map": "application/json",
    }
    return types.get(suffix, "application/octet-stream")


#: Minimal HTML shown when the SPA is not built yet — directs the
#: developer to run the build step.
_FALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Pylar Admin</title>
  <style>
    body { font-family: system-ui, sans-serif; display: flex; justify-content: center;
           align-items: center; min-height: 100vh; margin: 0; background: #0f172a; color: #94a3b8; }
    .box { text-align: center; }
    code { background: #1e293b; padding: 2px 8px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Pylar Admin</h1>
    <p>The SPA has not been built yet.</p>
    <p>Run <code>cd pylar/admin/spa && npm install && npm run build</code></p>
  </div>
</body>
</html>
"""
