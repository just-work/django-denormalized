""" Type definitions used in denormalized package."""
from typing import Dict, Tuple

from django.db import models
from django.db.models.expressions import Expression

# Type for incremental updates with field names as keys and F-objects values.
IncrementalUpdates = Dict[str, Expression]

# Type for update operation with an object to update and new values dict.
UpdateUnit = Tuple[models.Model, IncrementalUpdates]
