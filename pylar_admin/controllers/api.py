"""JSON API controller for the admin panel.

Provides RESTful endpoints for CRUD operations on registered models.
The Vue.js SPA consumes these endpoints to render the admin interface.

Routes (all prefixed by AdminConfig.prefix + /api):

    GET    /models                       → list registered models
    GET    /models/{slug}/schema         → field schema for a model
    GET    /models/{slug}/records        → paginated list (search, filter, sort)
    POST   /models/{slug}/records        → create record
    GET    /models/{slug}/records/{pk}   → single record
    PUT    /models/{slug}/records/{pk}   → update record
    DELETE /models/{slug}/records/{pk}   → delete record
    GET    /dashboard                    → model counts
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc as sa_desc
from sqlalchemy import inspect as sa_inspect

from pylar_admin.config import AdminConfig
from pylar_admin.exceptions import ModelNotRegisteredError
from pylar_admin.registry import AdminRegistry
from pylar_admin.serializer import deserialize_form_data, serialize_instance
from pylar.database.model import Model
from pylar.database.session import current_session
from pylar.database.transaction import transaction
from pylar.foundation.container import Container
from pylar.http import JsonResponse, Request, Response
from pylar.scheduling.schedule import Schedule


class AdminApiController:
    """Stateless JSON API controller consumed by the Vue.js admin SPA.

    All methods are ``async def`` so they work with pylar's routing.
    The registry and config are injected by the container.
    """

    def __init__(
        self,
        registry: AdminRegistry,
        config: AdminConfig,
        container: Container | None = None,
    ) -> None:
        # ``container`` is declared as ``Container | None`` because
        # some tests (and older provider wiring) construct the
        # controller directly without an application context. In the
        # live pipeline the :class:`AdminServiceProvider` registers
        # the controller with an explicit factory that passes the
        # app's container, so this path is never exercised in
        # production.
        self._registry = registry
        self._config = config
        self._container = container
        self._schedule: Schedule | None = None
        if container is not None and container.has(Schedule):
            self._schedule = container.make(Schedule)

    async def _check_permission(
        self, reg: Any, verb: str
    ) -> Response | None:
        """Return a 403 response if the current user lacks the verb permission.

        *verb* is one of ``view``, ``add``, ``change``, ``delete``. When
        the matching slot on :class:`AdminPermissions` is ``None`` (the
        default), the check is a no-op — all authenticated admins pass.
        Returns ``None`` on success so callers can ``return early`` on
        denial::

            if (denied := await self._check_permission(reg, "add")):
                return denied
        """
        code: str | None = getattr(reg.config.permissions, verb, None)
        if code is None:
            return None

        from pylar.auth.context import current_user_or_none

        user = current_user_or_none()
        if user is None:
            return JsonResponse(
                {"error": "Unauthenticated", "code": 401}, status_code=401,
            )
        if not await _user_has_permission(user, code):
            return JsonResponse(
                {"error": f"Permission denied: {code}", "code": 403},
                status_code=403,
            )
        return None

    # ----------------------------------------------------------- dashboard

    async def dashboard(self, request: Request) -> Response:
        """Return model counts for the dashboard view."""
        session = current_session()
        results: list[dict[str, Any]] = []
        for reg in self._registry.all_registrations():
            count = await reg.model.query.count(session=session)
            results.append({
                "slug": reg.slug,
                "label": reg.label,
                "label_plural": reg.label_plural,
                "count": count,
            })
        return JsonResponse({"models": results})

    # ----------------------------------------------------------- model listing

    async def models_index(self, request: Request) -> Response:
        """Return a list of all registered models with their slugs."""
        models = [
            {
                "slug": reg.slug,
                "label": reg.label,
                "label_plural": reg.label_plural,
            }
            for reg in self._registry.all_registrations()
        ]
        return JsonResponse({"models": models})

    async def model_schema(self, request: Request, slug: str) -> Response:
        """Return field metadata for the Vue.js form/table generator.

        Each field gets a computed ``label`` — priority is
        ``admin.model.<slug>.field.<name>`` from the translator,
        falling through to the SQL column ``comment`` (set via
        ``fields.Field(comment=...)``), and finally the raw field
        name. That mirrors the way model labels already resolve in
        the menu endpoint.
        """
        try:
            schema = self._registry.model_schema(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        for field in schema["fields"]:
            translation_key = f"admin.model.{slug}.field.{field['name']}"
            translated = self._translate_maybe(translation_key, "")
            if translated:
                field["label"] = translated
            elif field.get("comment"):
                field["label"] = field["comment"]
            else:
                field["label"] = field["name"]

        return JsonResponse(schema)

    # ----------------------------------------------------------- records CRUD

    async def records_index(self, request: Request, slug: str) -> Response:
        """Paginated, searchable, sortable list of records."""
        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        if (denied := await self._check_permission(reg, "view")) is not None:
            return denied

        params = request.query_params
        page = int(params.get("page", "1"))
        per_page = int(
            params.get("per_page", str(reg.config.per_page or self._config.per_page))
        )
        search = params.get("search", "").strip()
        sort = params.get("sort", "")
        filter_params = {
            k.removeprefix("filter["): v
            for k, v in params.items()
            if k.startswith("filter[") and k.endswith("]") and v
        }

        session = current_session()
        qs = reg.model.query.where()

        # Apply search across search_fields.
        if search and reg.config.search_fields:
            from sqlalchemy import or_

            conditions = []
            for field_name in reg.config.search_fields:
                col_attr = getattr(reg.model, field_name, None)
                if col_attr is not None:
                    conditions.append(col_attr.ilike(f"%{_escape_like(search)}%"))
            if conditions:
                qs = qs.where(or_(*conditions))

        # Apply filters.
        for field_name, value in filter_params.items():
            col_attr = getattr(reg.model, field_name, None)
            if col_attr is not None:
                qs = qs.where(col_attr == value)

        # Apply sorting.
        if sort:
            if sort.startswith("-"):
                col_attr = getattr(reg.model, sort[1:], None)
                if col_attr is not None:
                    qs = qs.order_by(sa_desc(col_attr))
            else:
                col_attr = getattr(reg.model, sort, None)
                if col_attr is not None:
                    qs = qs.order_by(col_attr)
        elif reg.config.ordering:
            for order_expr in reg.config.ordering:
                if order_expr.startswith("-"):
                    col_attr = getattr(reg.model, order_expr[1:], None)
                    if col_attr is not None:
                        qs = qs.order_by(sa_desc(col_attr))
                else:
                    col_attr = getattr(reg.model, order_expr, None)
                    if col_attr is not None:
                        qs = qs.order_by(col_attr)

        paginator = await qs.paginate(
            page=page, per_page=per_page, session=session
        )
        items = [serialize_instance(item) for item in paginator.items]

        return JsonResponse({
            "data": items,
            "meta": {
                "current_page": paginator.current_page,
                "last_page": paginator.last_page,
                "per_page": paginator.per_page,
                "total": paginator.total,
            },
        })

    async def record_show(self, request: Request, slug: str, pk: str) -> Response:
        """Return a single record by primary key."""
        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        if (denied := await self._check_permission(reg, "view")) is not None:
            return denied

        session = current_session()
        pk_value = _coerce_pk(reg.model, pk)
        try:
            instance = await reg.model.query.get(pk_value, session=session)
        except Exception:
            return JsonResponse({"error": "Record not found"}, status_code=404)

        return JsonResponse({"data": serialize_instance(instance)})

    async def record_create(self, request: Request, slug: str) -> Response:
        """Create a new record from JSON body."""
        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        if (denied := await self._check_permission(reg, "add")) is not None:
            return denied

        body = await request.json()
        attrs = deserialize_form_data(
            reg.model,
            body,
            fields=reg.config.form_fields,
            readonly=reg.config.readonly_fields,
        )

        session = current_session()
        instance = reg.model(**attrs)
        async with transaction():
            await reg.model.query.save(instance, session=session)

        return JsonResponse(
            {"data": serialize_instance(instance)},
            status_code=201,
        )

    async def record_update(self, request: Request, slug: str, pk: str) -> Response:
        """Update an existing record from JSON body."""
        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        if (denied := await self._check_permission(reg, "change")) is not None:
            return denied

        pk_value = _coerce_pk(reg.model, pk)
        session = current_session()
        try:
            instance = await reg.model.query.get(pk_value, session=session)
        except Exception:
            return JsonResponse({"error": "Record not found"}, status_code=404)

        body = await request.json()
        attrs = deserialize_form_data(
            reg.model,
            body,
            fields=reg.config.form_fields,
            readonly=reg.config.readonly_fields,
        )
        for key, value in attrs.items():
            setattr(instance, key, value)

        async with transaction():
            await reg.model.query.save(instance, session=session)

        return JsonResponse({"data": serialize_instance(instance)})

    async def record_delete(self, request: Request, slug: str, pk: str) -> Response:
        """Delete a record by primary key."""
        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse({"error": f"Model {slug!r} not found"}, status_code=404)

        if (denied := await self._check_permission(reg, "delete")) is not None:
            return denied

        pk_value = _coerce_pk(reg.model, pk)
        session = current_session()
        try:
            instance = await reg.model.query.get(pk_value, session=session)
        except Exception:
            return JsonResponse({"error": "Record not found"}, status_code=404)

        async with transaction():
            await reg.model.query.delete(instance, session=session)

        return JsonResponse({"message": "Deleted"})

    # ----------------------------------------------------------- actions

    async def actions_index(self, request: Request, slug: str) -> Response:
        """List the admin actions registered on *slug*'s ModelAdmin.

        The SPA calls this on the list view to render the action
        dropdown; the response mirrors what :meth:`run_action` expects
        in its ``name`` path parameter.
        """
        from pylar_admin.actions import resolve_actions

        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse(
                {"error": f"Model {slug!r} not found"}, status_code=404,
            )
        actions = resolve_actions(reg.config.actions)
        payload = [
            {
                "name": action.name,
                "label": action.label,
                "confirm": action.confirm,
                "description": action.description,
            }
            for action in actions
        ]
        return JsonResponse({"actions": payload})

    async def run_action(
        self, request: Request, slug: str, name: str,
    ) -> Response:
        """Run the named action against the selected row ids.

        Body: ``{"ids": [1, 2, 3]}``. The matched rows are loaded and
        passed to the action handler; its :class:`ActionResult` is
        rendered as JSON (or streamed as a download for file exports).
        """
        from pylar_admin.actions import ActionResult, resolve_actions

        try:
            reg = self._registry.get(slug)
        except ModelNotRegisteredError:
            return JsonResponse(
                {"error": f"Model {slug!r} not found"}, status_code=404,
            )

        resolved = {a.name: a for a in resolve_actions(reg.config.actions)}
        action = resolved.get(name)
        if action is None:
            return JsonResponse(
                {"error": f"Action {name!r} not registered"}, status_code=404,
            )

        body = await request.json()
        raw_ids = body.get("ids", []) if isinstance(body, dict) else []
        if not isinstance(raw_ids, list) or not raw_ids:
            return JsonResponse(
                {"error": "ids must be a non-empty list"}, status_code=400,
            )

        coerced = [_coerce_pk(reg.model, str(rid)) for rid in raw_ids]
        session = current_session()
        mapper = sa_inspect(reg.model)
        pk_key = mapper.primary_key[0].key
        if pk_key is None:
            return JsonResponse(
                {"error": "model has no primary key"}, status_code=500,
            )
        pk_col = getattr(reg.model, pk_key)
        records = list(
            await reg.model.query.where(pk_col.in_(coerced)).all(session=session)
        )

        try:
            result = await action.handler(records, request=request)
        except Exception as exc:
            return JsonResponse(
                {"status": "error", "message": str(exc)}, status_code=500,
            )
        if not isinstance(result, ActionResult):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "action returned a non-ActionResult value",
                },
                status_code=500,
            )
        return result.to_response()


    # ----------------------------------------------------------- menu

    async def menu(self, request: Request) -> Response:
        """Return the admin navigation tree with per-item metadata.

        The SPA pulls this endpoint once at boot (after ``/user``
        succeeds) and renders the sidebar from the response. Moving
        the menu server-side means pages that do not call
        ``/dashboard`` — like System → Cron — still get the full
        model list on reload.

        Every entry carries a ``kind`` discriminator:

        * ``"link"``   — a plain leaf in the top level, Vue resolves
                         ``route`` via ``vue-router``.
        * ``"section"``— a header followed by ``items`` of kind
                         ``"link"``.

        Section and link labels are translated through the bound
        :class:`pylar.i18n.Translator` when one is available —
        :class:`AcceptLanguageMiddleware` sets the active locale from
        the request before this handler runs. Applications override
        specific strings by dropping their own
        ``resources/lang/<locale>/admin.json`` file next to the
        catalogues shipped with ``pylar-admin``.
        """
        t = self._translate
        models_section: dict[str, Any] = {
            "kind": "section",
            "label": t("admin.models", "Models"),
            "items": [
                {
                    "kind": "link",
                    # Per-model labels try the translator first, then
                    # fall back to whatever the ModelAdmin resolved.
                    # Convention: ``admin.model.<slug>.plural`` /
                    # ``admin.model.<slug>.singular`` — applications
                    # override by dropping keys into their own
                    # ``resources/lang/<locale>/admin.json``.
                    "label": self._translate_maybe(
                        f"admin.model.{reg.slug}.plural", reg.label_plural,
                    ),
                    "route": {
                        "name": "model-list",
                        "params": {"slug": reg.slug},
                    },
                    "meta": {
                        "slug": reg.slug,
                        "label_singular": self._translate_maybe(
                            f"admin.model.{reg.slug}.singular", reg.label,
                        ),
                    },
                }
                for reg in self._registry.all_registrations()
            ],
        }
        system_section: dict[str, Any] = {
            "kind": "section",
            "label": t("admin.system", "System"),
            "items": [
                {
                    "kind": "link",
                    "label": t("admin.cron", "Cron"),
                    "route": {"name": "system-cron"},
                    "meta": {
                        "description": t(
                            "admin.cron_description",
                            "Scheduler task list",
                        ),
                    },
                },
                {
                    "kind": "link",
                    "label": t("admin.queues", "Queues"),
                    "route": {"name": "system-queues"},
                    "meta": {
                        "description": t(
                            "admin.queues_description",
                            "Queue backlog and failed jobs",
                        ),
                    },
                },
                {
                    "kind": "link",
                    "label": t("admin.webauthn", "Passkeys"),
                    "route": {"name": "system-webauthn"},
                    "meta": {
                        "description": t(
                            "admin.webauthn_description",
                            "Registered WebAuthn credentials",
                        ),
                    },
                },
            ],
        }
        payload: dict[str, Any] = {
            "items": [
                {
                    "kind": "link",
                    "label": t("admin.dashboard", "Dashboard"),
                    "route": {"name": "dashboard"},
                    "meta": {},
                },
                models_section,
                system_section,
            ],
        }
        return JsonResponse(payload)

    def _translate(self, key: str, fallback: str) -> str:
        """Resolve *key* through the bound Translator or return *fallback*.

        Admin endpoints must keep working without the i18n layer
        installed. When no :class:`Translator` is in the container we
        simply return the fallback, which means the panel renders in
        English out of the box.
        """
        return self._translate_maybe(key, fallback)

    def _translate_maybe(self, key: str, fallback: str) -> str:
        """Same contract as :meth:`_translate`, kept as a second name so
        callers can signal "fall back on miss" intent explicitly.

        Used for model labels where the catalogue entry may be absent
        (a project that hasn't translated a given model yet) — the
        fallback is then whatever the ModelAdmin resolved for that
        model, which is already a reasonable human-readable name.
        """
        if self._container is None:
            return fallback
        try:
            from pylar.i18n.translator import Translator
        except ImportError:
            return fallback
        if not self._container.has(Translator):
            return fallback
        translator = self._container.make(Translator)
        message = translator.get(key)
        # Translator returns the raw key when it's missing — we
        # surface the prettier fallback in that case.
        return message if message != key else fallback

    # ----------------------------------------------------------- system

    async def schedule_list(self, request: Request) -> Response:
        """Return the application's cron schedule as a JSON list.

        Powers the admin panel's System → Cron page. Each entry
        includes the cron expression, human label (falls back to the
        task's ``describe()`` output), timezone name, and the
        computed next fire time in UTC ISO-8601. When the scheduling
        module is not installed the endpoint simply returns an empty
        list so the page renders cleanly rather than 500-ing.
        """
        from datetime import UTC, datetime

        if self._schedule is None:
            return JsonResponse({"tasks": []})

        now = datetime.now(UTC)
        tasks: list[dict[str, Any]] = []
        for task in self._schedule.tasks():
            try:
                next_run = task.next_run_at(now).astimezone(UTC).isoformat()
            except Exception:
                next_run = None
            tz_name = (
                getattr(task.timezone, "key", str(task.timezone))
                if task.timezone is not None
                else "UTC"
            )
            interval = task.interval_seconds
            tasks.append({
                "name": task.name,
                "description": task.describe(),
                # ``cron`` is omitted (null) for interval-based tasks
                # so the UI doesn't render a misleading "* * * * *"
                # that never actually runs. The ``interval_seconds``
                # field covers that case instead.
                "cron": task.cron_expression if interval is None else None,
                "interval_seconds": interval,
                "schedule_kind": "interval" if interval is not None else "cron",
                "timezone": tz_name,
                "next_run_at": next_run,
                "type": type(task).__name__,
            })
        return JsonResponse({"tasks": tasks})


def _coerce_pk(model: type[Model], raw: str) -> object:
    """Coerce a raw string PK to the model's primary key type."""
    import uuid as _uuid

    mapper = sa_inspect(model)
    pk_col = mapper.primary_key[0]
    if isinstance(pk_col.type, sa_inspect(model).primary_key[0].type.__class__):
        pass
    # Try int first, then UUID, then leave as string.
    try:
        return int(raw)
    except (ValueError, TypeError):
        pass
    try:
        return _uuid.UUID(raw)
    except (ValueError, TypeError):
        pass
    return raw


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _user_has_permission(user: Any, code: str) -> bool:
    """Check whether *user* holds permission *code*.

    When the user exposes a ``permission_codes`` coroutine (used by
    custom auth setups and tests), that set is consulted directly —
    wildcard suffixes like ``posts.*`` match any ``posts.<verb>``.
    Otherwise the standard :func:`pylar.auth.roles.has_permission`
    helper runs its DB query over the roles/permissions pivot tables.
    """
    codes_fn = getattr(user, "permission_codes", None)
    if codes_fn is not None:
        codes = await codes_fn()
        if code in codes:
            return True
        for granted in codes:
            if granted.endswith(".*") and code.startswith(granted[:-1]):
                return True
        return False
    from pylar.auth.roles import has_permission

    return await has_permission(user, code)
