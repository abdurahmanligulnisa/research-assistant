"""
Spec-named alias for the storage repository module.

The spec requires this module to be named ``cache_store.py``.  The
implementation lives in ``repository.py`` (named after its role as a
database-backed *repository*, not an in-memory cache).  This shim
re-exports every public symbol so that code using either name works
identically.

Connection-pool note
--------------------
Pool state is managed via the module-level ``_pool`` variable and
``_get_pool()`` function in ``repository.py``; it is not an instance
attribute of :class:`ResearchRepository`.

Usage (spec-compliant import)::

    from src.storage.cache_store import repository, init_db, ResearchRepository

Usage (original name, also fine)::

    from src.storage.repository import repository, init_db, ResearchRepository
"""

from src.storage.repository import (  # noqa: F401  re-export all public names
    ResearchRepository,
    init_db,
    repository,
)

__all__ = ["ResearchRepository", "init_db", "repository"]
