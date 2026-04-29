"""Pylar Admin — optional Vue.js SPA admin panel with auto-CRUD.

Install: ``pip install pylar-admin``

The provider is auto-discovered via entry points — no need to add it
to ``config/app.py`` manually.  To disable, uninstall the package or
set ``AdminConfig.enabled = False``.

Register models for admin access, and the panel auto-generates list,
detail, create, and edit views with search, filtering, sorting, and
pagination — all driven by a JSON API consumed by the bundled Vue.js SPA.
"""

from pylar_admin.actions import (
    ActionResult,
    AdminAction,
    ExportCsvAction,
    ExportJsonAction,
    admin_action,
    resolve_actions,
)
from pylar_admin.config import AdminConfig, AdminPermissions, ModelAdmin
from pylar_admin.exceptions import AdminConfigError, AdminError, ModelNotRegisteredError
from pylar_admin.provider import AdminServiceProvider
from pylar_admin.registry import AdminRegistry
from pylar_admin.site import AdminSite

__all__ = [
    "ActionResult",
    "AdminAction",
    "AdminConfig",
    "AdminConfigError",
    "AdminError",
    "AdminPermissions",
    "AdminRegistry",
    "AdminServiceProvider",
    "AdminSite",
    "ExportCsvAction",
    "ExportJsonAction",
    "ModelAdmin",
    "ModelNotRegisteredError",
    "admin_action",
    "resolve_actions",
]
