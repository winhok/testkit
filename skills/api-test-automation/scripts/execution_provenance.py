"""Runner-produced metadata; no dependency on the optional acceptance package."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ExecutionProvenance:
    def __init__(self, definition, *, target_url, inputs=()):
        self.definition = Path(definition)
        self.paths = list(dict.fromkeys([self.definition, *map(Path, inputs)]))
        self.before = {p: file_sha256(p) for p in self.paths}
        self.target_url = target_url
        self.started_at = datetime.now(timezone.utc).isoformat()

    def finish(self):
        try:
            unchanged = all(file_sha256(p) == h for p, h in self.before.items())
        except OSError:
            unchanged = False
        return {"started_at": self.started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "definition_sha256": self.before[self.definition],
                "input_sha256": sorted(set(self.before.values())),
                "inputs_unchanged": unchanged, "target_url": self.target_url}
