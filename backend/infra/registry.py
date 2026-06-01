"""In-memory registry of instantiated adapters + cached routing rules.

Refreshes from DB when MAX(routing_rules.version) advances — that's our cheap
"is config stale" signal. Bumping a rule's version triggers a rebuild on the
next call from any adapter.
"""
import json, threading
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from infra import crypto, catalog


class Registry:
    def __init__(self):
        self._lock = threading.Lock()
        self._providers: dict[str, Any] = {}          # provider_id -> adapter instance
        self._provider_meta: dict[str, dict] = {}     # provider_id -> {surface, adapter_kind, name}
        self._rules: dict[tuple[str, str], dict] = {} # (surface, task) -> rule dict
        self._max_version = -1

    # ---------- Public API ----------
    def refresh_if_stale(self, db: Session) -> bool:
        """Returns True if a reload happened."""
        max_v = db.query(func.coalesce(func.max(models.RoutingRule.version), 0)).scalar() or 0
        if max_v == self._max_version:
            return False
        with self._lock:
            # Re-check inside the lock to avoid double reload
            if max_v == self._max_version:
                return False
            self._reload(db)
            self._max_version = max_v
        return True

    def get_provider(self, provider_id: str):
        return self._providers.get(provider_id)

    def get_provider_meta(self, provider_id: str) -> dict | None:
        return self._provider_meta.get(provider_id)

    def get_rule(self, surface: str, task: str) -> dict | None:
        """Look up a routing rule. Falls back to wildcard task '*' if no exact match."""
        return self._rules.get((surface, task)) or self._rules.get((surface, "*"))

    def all_provider_meta(self) -> dict[str, dict]:
        return dict(self._provider_meta)

    def invalidate(self):
        """Force next refresh_if_stale to reload."""
        with self._lock:
            self._max_version = -1

    # ---------- Private ----------
    def _reload(self, db: Session):
        new_providers = {}
        new_meta = {}
        for p in db.query(models.ProviderConfig).filter(models.ProviderConfig.enabled == True).all():
            try:
                cfg = json.loads(crypto.decrypt(p.config_json))
                adapter = catalog.build_adapter(p.adapter_kind, cfg)
                new_providers[p.id] = adapter
                new_meta[p.id] = {
                    "id": p.id,
                    "name": p.name,
                    "surface": p.surface,
                    "adapter_kind": p.adapter_kind,
                }
            except Exception as e:
                # Don't let one broken provider take the whole registry down
                print(f"[registry] failed to load provider {p.name} ({p.adapter_kind}): {e}")
                continue

        new_rules = {}
        for r in db.query(models.RoutingRule).all():
            try:
                new_rules[(r.surface, r.task)] = json.loads(r.rule_json)
            except Exception as e:
                print(f"[registry] failed to parse rule {r.surface}/{r.task}: {e}")

        self._providers = new_providers
        self._provider_meta = new_meta
        self._rules = new_rules
        print(f"[registry] reloaded: {len(new_providers)} providers, {len(new_rules)} rules")


_registry = Registry()


def get_registry() -> Registry:
    return _registry
