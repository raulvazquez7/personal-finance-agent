"""Benchmark metrics over (golden, predicted) rows; a pure function (spec 13.1)."""

from uuid import UUID

from pydantic import BaseModel

from finance.categorization.jev_questions import match_key

BUCKETS = ((0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01))
THRESHOLDS = (0.8, 0.85, 0.9, 0.95)


class EvalRow(BaseModel):
    transaction_id: UUID
    text: str
    outgoing: bool
    golden_slug: str
    golden_level1: str
    golden_subscription: bool | None = None
    golden_merchant: str | None = None
    predicted_slug: str
    predicted_level1: str
    confidence: float | None
    level1_confidence: float | None
    predicted_subscription: bool
    subscription_score: float | None
    predicted_merchant: str | None


class Bucket(BaseModel):
    low: float
    high: float
    rows: int
    right: int


class ThresholdResult(BaseModel):
    threshold: float
    accepted: int
    wrong: int
    review: int

    def precision(self) -> float | None:
        return 1 - self.wrong / self.accepted if self.accepted else None


class LevelMetrics(BaseModel):
    right: int
    total: int
    buckets: list[Bucket]
    thresholds: list[ThresholdResult]

    def accuracy(self) -> float:
        return self.right / self.total if self.total else 0.0

    def at(self, threshold: float) -> ThresholdResult:
        return next(t for t in self.thresholds if t.threshold == threshold)


class Ratio(BaseModel):
    hits: int
    total: int


class Metrics(BaseModel):
    rows: int
    level2: LevelMetrics
    level1: LevelMetrics
    subscription_precision: Ratio
    subscription_recall: Ratio
    merchant: Ratio


def _level(scored: list[tuple[bool, float]]) -> LevelMetrics:
    buckets = []
    for low, high in BUCKETS:
        inside = [right for right, confidence in scored if low <= confidence < high]
        buckets.append(Bucket(low=low, high=high, rows=len(inside), right=sum(inside)))
    thresholds = []
    for threshold in THRESHOLDS:
        accepted = [right for right, confidence in scored if confidence >= threshold]
        thresholds.append(
            ThresholdResult(
                threshold=threshold,
                accepted=len(accepted),
                wrong=accepted.count(False),
                review=len(scored) - len(accepted),
            )
        )
    return LevelMetrics(
        right=sum(right for right, _ in scored),
        total=len(scored),
        buckets=buckets,
        thresholds=thresholds,
    )


def compute_metrics(rows: list[EvalRow]) -> Metrics:
    level2 = [(r.predicted_slug == r.golden_slug, r.confidence or 0.0) for r in rows]
    level1 = [(r.predicted_level1 == r.golden_level1, r.level1_confidence or 0.0) for r in rows]
    # Subscriptions are expenses only, as in the categorizer (spec 5.2).
    labelled = [r for r in rows if r.golden_subscription is not None]
    flagged = [r for r in labelled if r.outgoing and r.predicted_subscription]
    truly = [r for r in labelled if r.golden_subscription]
    named = [r for r in rows if r.golden_merchant]
    return Metrics(
        rows=len(rows),
        level2=_level(level2),
        level1=_level(level1),
        subscription_precision=Ratio(
            hits=sum(r.golden_subscription for r in flagged), total=len(flagged)
        ),
        subscription_recall=Ratio(
            hits=sum(r.outgoing and r.predicted_subscription for r in truly), total=len(truly)
        ),
        merchant=Ratio(
            hits=sum(
                bool(r.predicted_merchant)
                and match_key(r.predicted_merchant) == match_key(r.golden_merchant)
                for r in named
            ),
            total=len(named),
        ),
    )
