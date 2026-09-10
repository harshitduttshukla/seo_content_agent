"""Test that declarative models inherit eager_defaults to prevent MissingGreenlet in async."""

from app.db.base import Base
from app.domains.content.models import ContentPage
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.domains.websites.models import Website


def test_base_has_eager_defaults() -> None:
    """Verify Declarative Base specifies eager_defaults=True."""
    assert getattr(Base, "__mapper_args__", {}).get("eager_defaults") is True


def test_domain_models_inherit_eager_defaults() -> None:
    """Ensure all core domain models inherit eager_defaults=True."""
    models = [
        SEOStrategy,
        SEOStrategyVersion,
        Project,
        Organization,
        Website,
        ContentPage,
    ]
    for model in models:
        assert model.__mapper__.eager_defaults is True, (
            f"{model.__name__} does not have eager_defaults=True"
        )
