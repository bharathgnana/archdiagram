"""Vendor service catalog and icon resolution."""

from .catalog import Catalog, ServiceEntry, get_catalog
from .icons import IconResolver, IconRef

__all__ = ["Catalog", "ServiceEntry", "get_catalog", "IconResolver", "IconRef"]
