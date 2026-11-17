"""The generic annotation unit.

A trace becomes an ordered list of units. A unit holds named fields. Both the
unit and each field can be an annotation target, because formats differ on
where the interesting thing lives: our coordinator puts reasoning and the
delegated question in one step, while Who&When labels the run as a whole.

Fields carry a stable `name` as well as a display `label`, because the name is
what an annotation is keyed on and must survive relabelling in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Field:
    name: str                      # stable id, e.g. "reasoning"
    label: str                     # shown to the annotator, e.g. "Reasoning"
    value: str
    style: str = "plain"           # plain | quote | code | muted
    kind: str = "text"             # text | category | number | flag

    @property
    def is_empty(self) -> bool:
        return self.value in (None, "", "None")


@dataclass
class Unit:
    key: str                       # stable within a trace, e.g. "coord_r1"
    kind: str                      # adapter vocabulary: decision, tool, reply ...
    title: str
    fields: list[Field] = field(default_factory=list)
    actor: str = ""
    badge: str = ""
    depth: int = 0                 # nesting, for formats that carry a tree
    meta: dict = field(default_factory=dict)

    def get(self, name: str) -> str:
        return next((f.value for f in self.fields if f.name == name), "")

    def text(self) -> str:
        """Flattened content, for the LLM prompt and for search."""
        return "\n".join(f"{f.label}: {f.value}" for f in self.fields if not f.is_empty)


@dataclass
class Trace:
    """One annotatable run, whatever the source format called it."""
    id: str
    title: str
    units: list[Unit] = field(default_factory=list)
    fields: list[Field] = field(default_factory=list)   # annotatable at run level
    meta: dict = field(default_factory=dict)            # display only
    raw: dict = field(default_factory=dict)

    def unit(self, key: str) -> Unit | None:
        return next((u for u in self.units if u.key == key), None)

    def field_names(self) -> dict[str, list[str]]:
        """Field names per unit kind, for the configure screen."""
        out: dict[str, list[str]] = {}
        for u in self.units:
            seen = out.setdefault(u.kind, [])
            for f in u.fields:
                if f.name not in seen:
                    seen.append(f.name)
        return out
