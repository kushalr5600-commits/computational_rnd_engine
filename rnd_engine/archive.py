from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .models import Candidate


class Archive:
    def __init__(
        self,
        path: str = "artifacts/archive.jsonl",
        max_size: int = 5000,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self.items: list[Candidate] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            try:
                candidate = Candidate.model_validate_json(line)
            except ValidationError:
                continue

            self.items.append(candidate)

        self.items = self.items[-self.max_size :]
        self.items.sort(
            key=lambda item: item.score.omega if item.score else 0.0,
            reverse=True,
        )

    def add(self, candidate: Candidate) -> None:
        if candidate.score is None:
            return

        self.items.append(candidate)
        self.items.sort(
            key=lambda item: item.score.omega if item.score else 0.0,
            reverse=True,
        )
        self.items = self.items[: self.max_size]

        with self.path.open("w", encoding="utf-8") as file:
            for item in self.items:
                file.write(item.model_dump_json())
                file.write("\n")

    def designs(self) -> list:
        return [item.design for item in self.items]

    def best(self, n: int = 10) -> list[Candidate]:
        return self.items[:n]
