"""Catálogo de regras de transição lido do `.env` (§8 CONVENTION.md).

ID estável: `uuid5(NAMESPACE_DNS, "<from_role>__<to_role>")` — permite GET por ID sem persistir.
Validação acontece no import (boot do app); `.env` inválido derruba o serviço com erro claro.
"""

from dataclasses import dataclass
from uuid import UUID, uuid5, NAMESPACE_DNS

from app.config import settings


class RoleRulesConfigError(ValueError):
    """`.env` ROLE_RULES inválido — interrompe boot."""


@dataclass(frozen=True, slots=True)
class RuleSpec:
    id: UUID
    from_role: str | None
    to_role: str
    mode: str  # "add" | "replace"
    requires_role: str | None
    forbids_role: str | None
    blocking: bool

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "from_role": self.from_role,
            "to_role": self.to_role,
            "mode": self.mode,
            "requires_role": self.requires_role,
            "forbids_role": self.forbids_role,
            "blocking": self.blocking,
        }


def _rule_id(from_role: str | None, to_role: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"{from_role or ''}__{to_role}")


def _build_rules() -> tuple[RuleSpec, ...]:
    rules: list[RuleSpec] = []
    seen: set[UUID] = set()
    for idx, raw in enumerate(settings.ROLE_RULES):
        to_role = raw.get("to_role")
        if not to_role:
            raise RoleRulesConfigError(f"ROLE_RULES[{idx}]: 'to_role' é obrigatório")
        mode = raw.get("mode")
        if mode not in ("add", "replace"):
            raise RoleRulesConfigError(
                f"ROLE_RULES[{idx}]: 'mode' deve ser 'add' ou 'replace' (recebido: {mode!r})"
            )
        from_role = raw.get("from_role")
        if mode == "replace" and not from_role:
            raise RoleRulesConfigError(
                f"ROLE_RULES[{idx}]: mode='replace' exige 'from_role' não nulo"
            )
        rid = _rule_id(from_role, to_role)
        if rid in seen:
            raise RoleRulesConfigError(
                f"ROLE_RULES[{idx}]: duplicada {from_role!r} -> {to_role!r}"
            )
        seen.add(rid)
        rules.append(
            RuleSpec(
                id=rid,
                from_role=from_role,
                to_role=to_role,
                mode=mode,
                requires_role=raw.get("requires_role"),
                forbids_role=raw.get("forbids_role"),
                blocking=bool(raw.get("blocking", False)),
            )
        )
    return tuple(rules)


_RULES: tuple[RuleSpec, ...] = _build_rules()


def all_rules() -> tuple[RuleSpec, ...]:
    return _RULES


def get_rule_by_id(rule_id: UUID) -> RuleSpec | None:
    for r in _RULES:
        if r.id == rule_id:
            return r
    return None


def find_rule(*, to_role: str, from_role: str | None) -> RuleSpec | None:
    for r in _RULES:
        if r.to_role == to_role and r.from_role == from_role:
            return r
    return None


def find_promotion_rule(to_role: str) -> RuleSpec | None:
    for r in _RULES:
        if r.to_role == to_role and r.mode == "replace":
            return r
    return None


def find_any_rule(to_role: str) -> RuleSpec | None:
    for r in _RULES:
        if r.to_role == to_role:
            return r
    return None


def blocking_roles() -> frozenset[str]:
    return frozenset(r.to_role for r in _RULES if r.blocking)


def counts() -> dict[str, int]:
    return {
        "total": len(_RULES),
        "add": sum(1 for r in _RULES if r.mode == "add"),
        "replace": sum(1 for r in _RULES if r.mode == "replace"),
        "blocking": sum(1 for r in _RULES if r.blocking),
    }
