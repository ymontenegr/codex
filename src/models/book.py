from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Book:
    name: str
    path: Path
    id: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.path = Path(self.path)
