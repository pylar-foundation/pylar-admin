# pylar-admin

Vue.js SPA admin panel for the [pylar](https://pylar.dev) web framework.

## Installation

```bash
pip install pylar-admin
```

The admin provider is **auto-discovered** via entry points — no manual
changes to `config/app.py` needed. After installation, the admin panel
is available at `/admin/`.

## Usage

Register your models in a service provider's `boot()` method:

```python
from pylar_admin import AdminSite, ModelAdmin

async def boot(self, container: Container) -> None:
    site = container.make(AdminSite)
    site.register(Post)
    site.register(User, ModelAdmin(
        list_display=("id", "name", "email", "is_admin"),
        search_fields=("name", "email"),
    ))
```

## Disabling

Uninstall the package, or set `AdminConfig.enabled = False`:

```python
from pylar_admin import AdminConfig
container.instance(AdminConfig, AdminConfig(enabled=False))
```

## Features

- Auto-CRUD for registered SQLAlchemy models
- Vue.js 3 SPA with Pinia, Vue Router, TypeScript
- Search, filtering, sorting, pagination
- Dark/light mode
- Form auto-generation from model field introspection
- Authorization via pylar's Gate/Policy system
