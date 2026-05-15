from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Tag:
    name: str
    id: int = 0
    created_at: datetime = field(default_factory=datetime.now)
