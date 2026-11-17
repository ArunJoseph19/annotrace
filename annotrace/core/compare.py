"""Agreement between two sets of annotations.

Raw agreement alone flatters a schema whose labels are unevenly used: two
annotators who both answer "Yes" most of the time agree often by chance.
Cohen's kappa takes that chance rate out, so both are reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuestionAgreement:
    question_id: str
    prompt: str
    both: int = 0                       # steps both answered
    same: int = 0
    pairs: dict = field(default_factory=dict)   # (a, b) -> count

    @property
    def raw(self) -> float:
        return self.same / self.both if self.both else 0.0

    @property
    def kappa(self) -> float:
        """Cohen's kappa. Returns 0.0 when it cannot be computed."""
        if not self.both:
            return 0.0
        a_counts, b_counts = {}, {}
        for (a, b), n in self.pairs.items():
            a_counts[a] = a_counts.get(a, 0) + n
            b_counts[b] = b_counts.get(b, 0) + n
        expected = sum((a_counts.get(l, 0) / self.both) * (b_counts.get(l, 0) / self.both)
                       for l in set(a_counts) | set(b_counts))
        if expected >= 1.0:
            return 1.0 if self.raw >= 1.0 else 0.0
        return (self.raw - expected) / (1 - expected)

    @property
    def confusions(self) -> list[tuple[str, str, int]]:
        """Where they differed, commonest first."""
        return sorted(((a, b, n) for (a, b), n in self.pairs.items() if a != b),
                      key=lambda x: -x[2])


@dataclass
class Disagreement:
    trace_id: str
    unit_key: str
    question_id: str
    a: str
    b: str


@dataclass
class Report:
    questions: list[QuestionAgreement]
    disagreements: list[Disagreement]
    steps_a: int = 0
    steps_b: int = 0
    steps_both: int = 0

    @property
    def overall_raw(self) -> float:
        same = sum(q.same for q in self.questions)
        both = sum(q.both for q in self.questions)
        return same / both if both else 0.0

    @property
    def answers_compared(self) -> int:
        return sum(q.both for q in self.questions)


def strength(kappa: float) -> str:
    """The usual reading of a kappa value, so a number is not left bare."""
    if kappa < 0.0:
        return "worse than chance"
    if kappa < 0.21:
        return "slight"
    if kappa < 0.41:
        return "fair"
    if kappa < 0.61:
        return "moderate"
    if kappa < 0.81:
        return "substantial"
    return "almost perfect"


def compare(a: dict, b: dict, questions) -> Report:
    """`a` and `b` are {trace_id: {unit_key: record}}. `questions` comes from
    the schema, so a question one file has and the other lacks is still named."""
    per_q = {q.id: QuestionAgreement(q.id, q.prompt) for q in questions}
    diffs: list[Disagreement] = []

    keys_a = {(t, u) for t, units in a.items() for u in units}
    keys_b = {(t, u) for t, units in b.items() for u in units}

    for trace_id, unit_key in sorted(keys_a & keys_b):
        ra = a[trace_id][unit_key].get("labels") or {}
        rb = b[trace_id][unit_key].get("labels") or {}
        for qid, agreement in per_q.items():
            va, vb = ra.get(qid), rb.get(qid)
            if not va or not vb:
                continue           # one of them left it blank: nothing to compare
            agreement.both += 1
            agreement.pairs[(va, vb)] = agreement.pairs.get((va, vb), 0) + 1
            if va == vb:
                agreement.same += 1
            else:
                diffs.append(Disagreement(trace_id, unit_key, qid, va, vb))

    return Report(questions=[q for q in per_q.values()],
                  disagreements=diffs,
                  steps_a=len(keys_a), steps_b=len(keys_b),
                  steps_both=len(keys_a & keys_b))
