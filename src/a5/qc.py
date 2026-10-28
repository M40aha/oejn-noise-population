"""Quality-control registry. Every check records a result; nothing is hidden."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import pandas as pd

SEVERITIES = ("PASS", "INFO", "WARNING", "ERROR", "UNRESOLVED")


@dataclass
class QCResult:
    check_id: str
    category: str      # source | structure | normalisation | integrity | physics | logic | cross_source | validation | mapping
    severity: str
    message: str
    n_affected: int = 0
    details: str = ""


@dataclass
class QCRegistry:
    results: list[QCResult] = field(default_factory=list)

    def add(self, check_id: str, category: str, severity: str, message: str,
            n_affected: int = 0, details: str = "") -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        self.results.append(QCResult(check_id, category, severity, message, int(n_affected), str(details)))

    def check(self, check_id: str, category: str, n_bad: int, ok_msg: str, bad_msg: str,
              bad_severity: str = "ERROR", details: str = "") -> None:
        """Record PASS when n_bad == 0, otherwise bad_severity."""
        if n_bad == 0:
            self.add(check_id, category, "PASS", ok_msg)
        else:
            self.add(check_id, category, bad_severity, bad_msg, n_bad, details)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(r) for r in self.results])

    def count(self, severity: str) -> int:
        return sum(r.severity == severity for r in self.results)
