"""AdminServiceProvider — wires the admin panel into the application.

Add this provider to your ``AppConfig.providers`` to enable the admin.
Remove it (or set ``AdminConfig.enabled = False``) to disable entirely.
The admin is an optional module — no other part of pylar depends on it.
"""

from __future__ import annotations

from pylar_admin.config import AdminConfig
from pylar_admin.controllers.api import AdminApiController
from pylar_admin.controllers.auth import AdminAuthController
from pylar_admin.controllers.queues import QueueController
from pylar_admin.registry import AdminRegistry
from pylar_admin.site import AdminSite
from pylar.foundation.container import Container
from pylar.foundation.provider import ServiceProvider
from pylar.routing.router import Router


class AdminServiceProvider(ServiceProvider):
    """Registers and boots the admin panel.

    During ``register`` (sync): binds AdminConfig, AdminRegistry, AdminSite,
    and AdminApiController as singletons.

    During ``boot`` (async): mounts admin routes on the application router
    with optional auth middleware.
    """

    def register(self, container: Container) -> None:
        # Allow pre-registered AdminConfig (e.g. from tests).
        if container.has(AdminConfig):
            config = container.make(AdminConfig)
        else:
            config = AdminConfig()
            container.instance(AdminConfig, config)

        if not config.enabled:
            return
        container.singleton(AdminRegistry, AdminRegistry)
        container.singleton(AdminSite, AdminSite)
        # Factory binding for the API controller so we can thread the
        # container into its constructor — the controller uses it to
        # lazy-resolve cross-module singletons (Schedule, etc.) that
        # may or may not be registered depending on which service
        # providers are loaded.
        container.singleton(
            AdminApiController,
            lambda: AdminApiController(
                registry=container.make(AdminRegistry),
                config=container.make(AdminConfig),
                container=container,
            ),
        )
        container.singleton(AdminAuthController, AdminAuthController)
        container.singleton(
            QueueController,
            lambda: QueueController(container=container),
        )

    async def boot(self, container: Container) -> None:
        try:
            config = container.make(AdminConfig)
        except Exception:
            return  # Admin not enabled.

        if not config.enabled:
            return

        # Merge the admin's own translation catalogues into the
        # application's Translator if i18n is wired. Safe no-op when
        # the i18n layer is absent.
        self._merge_admin_translations(container)

        site = container.make(AdminSite)
        router = container.make(Router)

        # Build middleware stack for admin routes.
        middleware_classes: list[type] = []

        # Accept-Language negotiation — must run before handlers so the
        # ambient locale is in place when they call translator.get().
        try:
            from pylar.i18n import AcceptLanguageMiddleware
            from pylar.i18n.translator import Translator

            if container.has(Translator):
                middleware_classes.append(AcceptLanguageMiddleware)
        except ImportError:
            pass

        # Database session — required for all queries.
        try:
            from pylar.database import DatabaseSessionMiddleware

            middleware_classes.append(DatabaseSessionMiddleware)
        except ImportError:
            pass

        # Session middleware — required for login/logout.
        try:
            from pylar.session import SessionMiddleware

            middleware_classes.append(SessionMiddleware)
        except ImportError:
            pass

        # CSRF protection — after session, before auth.
        try:
            from pylar.auth.csrf import CsrfMiddleware

            debug = getattr(self.app.config, "debug", True)
            csrf = CsrfMiddleware(secure=not debug)
            container.instance(CsrfMiddleware, csrf)
            middleware_classes.append(CsrfMiddleware)
        except ImportError:
            pass

        # Auth middleware — resolves user + enforces login.
        if config.require_auth:
            try:
                from pylar.auth import AuthMiddleware, RequireAuthMiddleware
                from pylar.auth.contracts import Guard

                container.make(Guard)  # type: ignore[type-abstract]
                middleware_classes.append(AuthMiddleware)
                middleware_classes.append(RequireAuthMiddleware)
            except Exception:
                pass

        site.urls(router, middleware=middleware_classes)

    @staticmethod
    def _merge_admin_translations(container: Container) -> None:
        """Load bundled admin translations into the application Translator.

        The admin panel ships English and Russian catalogues under
        ``pylar_admin/translations/<locale>/admin.json``. When the
        application has an :class:`I18nServiceProvider` installed we
        merge those catalogues into the shared Translator so handlers
        can resolve keys like ``admin.dashboard`` out of the box.
        Applications that want to override a string can drop their
        own ``resources/lang/<locale>/admin.json`` next to ours —
        those are loaded first by I18nServiceProvider, but our
        ``add_messages`` preserves existing keys (it only adds
        missing ones).
        """
        try:
            from pylar.i18n.translator import Translator
        except ImportError:
            return
        if not container.has(Translator):
            return

        import json
        from pathlib import Path

        translator = container.make(Translator)
        root = Path(__file__).resolve().parent / "translations"
        if not root.is_dir():
            return
        for locale_dir in sorted(root.iterdir()):
            if not locale_dir.is_dir():
                continue
            for catalogue_file in sorted(locale_dir.glob("*.json")):
                try:
                    payload = json.loads(
                        catalogue_file.read_text(encoding="utf-8"),
                    )
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                group = catalogue_file.stem
                # ``add_messages`` performs ``dict.update`` — to keep
                # any application-level override that
                # ``I18nServiceProvider`` already installed we first
                # drop keys that exist in the translator's own map.
                existing = set(translator._messages.get(locale_dir.name, {}))
                messages = {
                    f"{group}.{key}": value
                    for key, value in payload.items()
                    if isinstance(value, str)
                    and f"{group}.{key}" not in existing
                }
                if messages:
                    translator.add_messages(locale_dir.name, messages)

    async def shutdown(self, container: Container) -> None:
        pass  # No cleanup needed.
