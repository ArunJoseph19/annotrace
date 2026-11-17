# Annotation Handbook
**Multi-agent LLM failure attribution** · prompt v7

***

## The Four Labels

| Label | When to use |
|---|---|
| **Critical** | Root cause of the final failure. Fixing only this step would likely fix the output. Every failed trajectory must have at least one. Always include a sub-type. |
| **Error** | Contributes to failure but is not the root cause. Often downstream propagation of a Critical step. Fixing alone may be insufficient. |
| **Warning** | Redundant or wasteful action — 3rd+ repeated search, extra coordinator round, slightly imprecise answer. No new failure introduced. |
| **Informational** | Correct and necessary. Should remain unchanged during optimisation. A step can be decisive for success and still be Informational. |

> **Key distinction:** "Critical" means critical *error*, never critical *importance*. A correct step, even a decisive one, is always Informational.

***

## Step Definition

Each step bundles **thinking, action, and response** together as one unit and receives a **single label**. However, the reasoning field should specify *which part* within the step caused the issue — for example:

- "Thinking was correct (intended to find Director A), but the search query was too broad and returned irrelevant documents."
- "Search query was well-formed, but retrieved documents were noisy and misled the subsequent reasoning."

This distinction matters for downstream analysis even though the label applies to the whole step. It is the standard definition used across prior work and allows annotations to generalise across different benchmarks and agent architectures.

> **Note on misalignment within a step:** In some cases thinking is correct but the action is wrong (e.g. poor query formulation), or the action happens to be correct despite wrong reasoning. Label the step based on its contribution to the final failure, and explain the internal misalignment in the reasoning field. A step where reasoning is wrong but the action accidentally succeeds is still a risk — label it at least Warning if relevant.

***

## Decision Flowchart

**Step 0 — Check the step type first**
- `think` → apply Think Step Rules below
- `answer` / `final_answer` → label on output quality only; Warning due to search count is forbidden
- `search_and_info` → repeated-query rules apply; also apply Restart Rule
- `coordinator_thinking` / `expert_call` → continue to Step 1

**Step 1 — Did something go wrong?**
- No → **Informational** (if necessary) or **Warning** (if redundant)
- Yes → Step 2

**Step 2 — Is this the root cause? Would fixing only this step likely fix the final output?**
- Yes → **Critical** + sub-type
- No → Step 3

**Step 3 — Did it contribute to the final failure?**
- Yes → **Error**
- No → **Warning** (wrong but inconsequential)

> **Pro tip:** Work backwards. Read the final answer first, confirm it's wrong, then trace back to find the earliest step where something went wrong — that's your Critical.

***

## Error Propagation

When a Critical step introduces a wrong assumption or wrong result, subsequent steps that follow from that mistake are **Error** (propagation), not Critical. Only assign a second Critical if a **genuinely new and independent failure** is introduced — not merely a consequence of the first.

```
Example — sequential dependency:
  Step 1  coordinator assigns wrong sub-task          →  Critical (root cause)
  Step 2  expert follows the wrong sub-task           →  Error    (propagation)
  Step 3  coordinator uses wrong expert output        →  Error    (propagation)
  Step 4  final answer built on wrong info            →  Error    (propagation)
```

> One root Critical, multiple downstream Errors. The cascade rule applies: do not promote a propagated failure to Critical just because it feels significant.

***

## Restart Rule

When an agent **retries** a failed approach (e.g. re-issues a search query after getting no useful results), annotate as follows:

| Attempt | Label | Reason |
|---|---|---|
| All attempts except the last | **Warning** | Abandoned — result not used in the final output |
| The final attempt | **Critical** or **Error** | Its result feeds into the failure |

The last attempt is Critical if its output is the direct root cause of the wrong final answer. It is Error if a prior Critical introduced the root failure and this attempt merely propagated it.

```
Example (agent retries a search three times, uses result of 3rd attempt):
  Search attempt 1  →  Warning   (abandoned)
  Search attempt 2  →  Warning   (abandoned)
  Search attempt 3  →  Critical  (result used; wrong documents caused wrong answer)
```

> **Exception:** If a prior attempt returned misleading documents that the agent *carried forward* into later reasoning (rather than discarding), that attempt may be **Error** or **Critical** rather than Warning — because it did contribute to the failure.

> **Reconciliation with Search & Info Rules:** The Restart Rule takes precedence when the agent is clearly cycling through attempts and using only the final result. The Search & Info table (Error × 2, then Warning) applies to cases where no clear "restart" pattern is identifiable and all attempts equally feed into the failure.

***

## Search & Info Rules

| Occurrence | Label |
|---|---|
| 1st search returns irrelevant docs | **Error** |
| 2nd search — identical query, no strategy change | **Error** |
| 3rd+ search — same query repeated | **Warning** (pure waste) |
| Repeated search returns noisy/misleading docs causing wrong answer | **Error** or **Critical** (not Warning) |
| Repeated query that looks "correct" | Still **Warning** — repetition count alone determines this |

> **Note:** When the agent only uses the final search result to form its answer (standard LLM behaviour), apply the **Restart Rule** instead — prior attempts become Warning and the final attempt becomes Critical or Error.

***

## Think Step Rules

- **Rule A** — Almost never Warning. Thinking wastes no external resource. The search that follows may be Warning, but the thought is not.
- **Rule B** — Label on reasoning content, not on adjacent searches.
- **Rule C** — When in doubt, default to **Informational**. If the reasoning is not demonstrably wrong, it's Informational.
- **Rule D** — Think steps inside a Warning search loop are **Informational**. The Warning belongs on the `search_and_info` step, not the `think` step between them.

```
Pattern in a repeated-search loop:
  [sN]   (search_and_info)  same query          →  Warning       (wasteful action)
  [sN+1] (think)            "I'll try again"    →  Informational (reasoning is fine)
  [sN+2] (search_and_info)  same query          →  Warning       (wasteful action)
  [sN+3] (think)            "Still no results"  →  Informational (correct interpretation)
```

***

## Coordinator Rules

### Mid-trajectory transitions
| Situation | Label |
|---|---|
| Correct sub-task framing and assignment | **Informational** |
| Wrong sub-task or wrong expert — introduces new failure | **Critical** (Task decomposition or Expert Assignment) |
| Extra round caused by prior expert failure | **Warning** (wasteful overhead, not a new error) |

### Final answer / final coordinator step
| Situation | Label |
|---|---|
| Had enough correct info from experts but still produced wrong answer | **Critical** (Response Process) |
| Introduced a new incorrect factor not in any expert output | **Critical** (Response Process) |
| Merely propagated a prior expert error without adding a new mistake | **Error** |

### Cascade failures
Only one step is the root Critical. When a coordinator introduces a false framing, everything downstream that follows it is Error, not Critical. Only assign a second Critical if a genuinely new and independent failure is introduced.

***

## Sequential vs Parallel Chains

**Sequential** (each expert call depends on the previous):
- An error early propagates to all downstream steps
- Downstream steps following the wrong assumption → **Error**
- Typically one Critical (root) + multiple Errors (propagation)

**Parallel** (coordinator dispatches independent sub-questions):
- An error in expert A does not affect expert B's independent branch
- Expert B's steps can be **Informational** even in a failed trajectory
- Evaluate each branch independently
- **Multiple Criticals in parallel branches:** If two independent sub-tasks each retrieve a wrong answer, and the final answer fails because of both, both are Critical. The test is: "Would fixing only this step have fixed the final output?" If each sub-task is independently necessary, each failure is independently Critical.

```
Example — parallel branches, both fail:
  Expert A retrieves wrong director name    →  Critical (Expert Agent — interaction)
  Expert B retrieves wrong birth date       →  Critical (Expert Agent — interaction)
  Coordinator combines both wrong answers  →  Error    (propagation)
```

***

## Self-Correction and Local Correctness

When an agent notices a mistake mid-trajectory and attempts to self-correct, the correction may be:

- **Globally correct** — fixes the actual error and leads toward the right answer → label the correction step **Informational**
- **Locally correct but globally wrong** — the reasoning appears valid in isolation but pursues the wrong direction (e.g. rechecks a sub-answer that was wrong, but reconfirms the wrong value) → label as **Error** propagation, not Informational

> **Key test:** Is the self-correction working toward the correct final answer, or just internally consistent within a wrong framing? If the latter, it is still a failure step.

***

## Precision Failures

When the answer is factually reasonable but too coarse (e.g. "Mongolia" instead of "Khamag Mongol", "Wilhelm Röntgen" instead of full name):
- `answer` and `final_answer` → **Warning**
- Upstream reasoning that was logically correct → **Informational**
- Do not label the coordinator's correct identification as Critical

***

## Common Pitfalls

| Wrong | Right |
|---|---|
| Labelling a correct coordinator step Critical because it was "important" to success | Correct + necessary = Informational, always |
| Labelling think steps Warning because nearby searches are Warning | Think steps in Warning loops are Informational |
| Multiple Critical labels in a single cascade | One root Critical — everything downstream following the same mistake → Error |
| Labelling a precision failure (too coarse, not wrong) as Error or Critical | Precision failures → Warning throughout; upstream reasoning → Informational |
| Labelling an `answer` step Warning because nearby searches were repeated | Answer steps are never Warning due to search count |
| Labelling all retry attempts as Critical or Error | Only the final attempt is Critical/Error; prior abandoned attempts are Warning |
| Labelling a propagated downstream step as Critical | Error propagation ≠ new Critical; ask whether a genuinely new failure was introduced |
| Treating a self-correction as Informational when it stays within a wrong framing | Locally correct ≠ globally correct; test against the final answer direction |

***

## AI Annotation Support

The built-in AI label suggester (Groq/LLM) operates on documents retrieved within the trajectory. It does **not** have access to external knowledge and may therefore:
- Fail to detect hallucinations in coordinator thinking (e.g. false Doctor Who framing)
- Confirm wrong answers that are not contradicted by the retrieved docs

**Workaround:** For knowledge-intensive questions where the trajectory's retrieval clearly failed, verify the golden answer via a manual web search before finalising labels. This is especially important for questions about obscure facts, proper names, or niche cultural knowledge where the agent and the AI suggester may share the same blind spot.

> This limitation will be addressed in a future version by equipping the AI suggester with search capabilities.

***

## Critical Sub-types Reference

Every Critical label must include one of these sub-types in parentheses.

**Coordinator-level** (`coordinator_thinking`, `expert_call`, `final_answer`):
- `Centralized Agent — Task decomposition`
- `Centralized Agent — Subtask Generation`
- `Centralized Agent — Expert Assignment`
- `Centralized Agent — Response Process`

**Expert-level** (`think`, `search_and_info`, `answer`):
- `Expert Agent — reasoning`
- `Expert Agent — interaction`
- `Expert Agent — communication`

**Example format:**
```
coord_r1: Critical (Centralized Agent — Task decomposition) | Hallucinated Doctor Who framing not present in the question.
```

***

*For internal use — annotation team · prompt v7 · who&when benchmark*