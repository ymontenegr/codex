from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Chapter:
    name: str
    path: Path
    book_id: int = 0
    id: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.path = Path(self.path)
