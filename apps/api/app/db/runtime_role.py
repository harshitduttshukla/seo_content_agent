"""Startup guard: the API's database role must not be able to bypass row-level security.

PostgreSQL skips RLS for superusers and BYPASSRLS roles, and a table's owner may
switch its policies off (or is exempt from them unless FORCE is set). Tenant
isolation in the database therefore holds only when the runtime role is none of
these. Migrations run under a separate administration role that owns the schema.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class UnsafeDatabaseRole(RuntimeError):
    """The runtime database role could bypass row-level security."""


@dataclass(frozen=True, slots=True)
class RuntimeRole:
    name: str
    superuser: bool
    bypass_rls: bool
    owned_rls_tables: tuple[str, ...]

    def problems(self) -> list[str]:
        found = []
        if self.superuser:
            found.append("is a superuser")
        if self.bypass_rls:
            found.append("has BYPASSRLS")
        if self.owned_rls_tables:
            owned = ", ".join(self.owned_rls_tables[:5])
            more = len(self.owned_rls_tables) - 5
            found.append(
                f"owns RLS-protected tables ({owned}{f', +{more} more' if more > 0 else ''})"
            )
        return found


async def inspect_runtime_role(engine: AsyncEngine) -> RuntimeRole:
    async with engine.connect() as connection:
        role = (
            await connection.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()
        # Ownership includes membership in the owning role, which confers the same rights.
        owned = (
            await connection.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "WHERE c.relnamespace = 'public'::regnamespace "
                    "AND c.relkind IN ('r', 'p') AND c.relrowsecurity "
                    "AND pg_has_role(current_user, c.relowner, 'MEMBER') "
                    "ORDER BY c.relname"
                )
            )
        ).scalars()
        return RuntimeRole(role.rolname, role.rolsuper, role.rolbypassrls, tuple(owned))


async def assert_runtime_role_enforces_rls(engine: AsyncEngine) -> None:
    """Refuse to serve through a role that PostgreSQL RLS would not constrain.

    The error names the role and the reason, never the connection URL or password.
    """
    role = await inspect_runtime_role(engine)
    problems = role.problems()
    if problems:
        raise UnsafeDatabaseRole(
            f"Database role {role.name!r} {'; '.join(problems)}: row-level security would not "
            "apply. Run the API as the non-owner application role (see scripts/postgres-init.sql); "
            "keep the owner/superuser role for migrations only."
        )
