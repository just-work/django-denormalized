""" Type definitions used in denormalized package."""
from typing import Dict

from django.db.models.expressions import Expression

# Type for incremental updates with field names as keys and F-objects values.
IncrementalUpdates = Dict[str, Expression]
