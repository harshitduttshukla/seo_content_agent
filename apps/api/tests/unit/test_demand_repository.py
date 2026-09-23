from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.domains.demand.repository import DemandRepository
from sqlalchemy.dialects import postgresql


@pytest.mark.asyncio
async def test_demand_review_queue_orders_confidence_ascending_with_nulls_last() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    repository = DemandRepository(session)

    await repository.get_demand_nodes(uuid4(), uuid4())

    statement = session.execute.await_args.args[0]
    query_sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY demand_nodes.confidence ASC NULLS LAST, demand_nodes.text" in query_sql
