from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Document:
    name: str
    path: Path
    chapter_id: int = 0
    id: int = 0
    word_count: int = 0
    is_favorite: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.path = Path(self.path)
