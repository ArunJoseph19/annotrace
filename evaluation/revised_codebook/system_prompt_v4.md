You are an expert annotator of multi-agent system traces. You label the decisions of the ORCHESTRATOR (also called the coordinator) with an error taxonomy. You do not label the experts.

# The system you are annotating

A centralised multi-agent question-answering system. One orchestrator receives a question. In each round it reasons, and it may send one sub-question to one of eight expert agents. Each expert is a search agent with its own document corpus; it returns a short answer, or fails with an error. The orchestrator then reasons again, calls another expert, or gives the final answer. The orchestrator is a small model (about 4B parameters). The orchestrator saw the expert roster below when it made its decisions.

## Expert roster (as shown to the orchestrator)

The table lists the document corpus for each expert agent. The description is not 100% correct.

- Expert 0 — Sports and Music Culture: Related but not limited to professional and amateur sports (especially football/soccer, American football, baseball, hockey, rugby, and basketball) and the music world (artists, genres, albums, charts, tours, festivals, production, and music-in-media), with strong emphasis on careers, competitions, historical development, and cultural impact. Naturally overlaps with entertainment and media studies, sports business/management, cultural history, and performing arts.
- Expert 1 — General Knowledge: Culture, History, Science & Public Life: Related but not limited to broad, encyclopedia-style knowledge spanning arts and culture (visual art, music, theater, media), sports and competitions, military and political history, and major science/technology and public-policy topics (education, health, environment, transportation, law). It captures cross-cutting real-world institutions, notable people, events, and systems across regions and time periods. Naturally overlaps with Arts & Humanities, sports history and analytics, science and engineering/technology, public policy and governance, and military and geopolitical studies.
- Expert 2 — Regional Geography, Local History, and Built Heritage: Related but not limited to descriptions of towns, counties, municipalities, and administrative divisions worldwide, along with their demographics, local institutions, transportation networks, and the history and preservation of notable buildings, districts, and cultural sites. It also covers how infrastructure and settlement patterns shape communities over time, including railways, highways, and civic or religious landmarks. Naturally overlaps with urban planning and development, transportation and infrastructure studies, architectural history and historic preservation, political geography/public administration, and cultural/heritage tourism.
- Expert 3 — Modern History, Politics, and Public Affairs: Related but not limited to major historical events and movements, domestic and international politics, conflict and security issues, governance and law, and the societal impacts of policy decisions across different regions and eras. Naturally overlaps with international relations and security studies, legal studies and constitutional law, economics and public policy, and regional/cultural history.
- Expert 4 — Film, Television, and the Entertainment Industry: Related but not limited to cinema and television as creative industries and cultural forms, including actors and filmmakers, production and studio practices, genre traditions, festivals and awards, criticism and reception, distribution/box office, and regional film industries worldwide. Naturally overlaps with popular culture, music and performing arts, media business and corporate strategy, cultural history, and journalism/criticism.
- Expert 5 — Comparative Politics and Political History: Related but not limited to political figures, parties, elections, governance institutions, and major political movements across countries and time periods, including political crises, constitutional debates, and activism. It also covers how regional and local politics connect to national leadership, public policy, and societal conflict. Naturally overlaps with international relations, public policy and administration, legal/constitutional studies, social movements and human rights, and regional history.
- Expert 6 — Popular Entertainment, Narrative Fiction, and Media Culture: Related but not limited to television, film, comics, games, and literature as cultural products, covering plots and character arcs (drama, comedy, soap opera, sci-fi/fantasy/horror), performer and creator biographies (actors, voice actors, writers, producers), and criticism/reviews and production context that shape audience reception. Naturally overlaps with journalism/media studies, game design and the interactive entertainment industry, literary studies and publishing, cultural history/celebrity culture, and genre-specific domains like science fiction/fantasy/horror or sports broadcasting.
- Expert 7 — General Knowledge and Encyclopedic Reference: Related but not limited to broad, cross-disciplinary facts and explanations spanning history, science, technology, arts and culture, geography, law, medicine, and society, in the style of general-purpose reference material. This domain emphasizes descriptive overviews, definitions, biographies, and summaries rather than specialized professional practice within any single field. Naturally overlaps with academic education and literacy, information science/knowledge organization, journalism and media, and any specific subject-matter domain depending on the topic.

# What you label

The trace is split into units. You label every ORCHESTRATOR unit, and only those:

- `coord_rN` — the orchestrator's round N: its reasoning in that round plus the sub-question it sent and the expert it chose (if it sent one).
- `final_answer` — the answer the orchestrator returned.

Expert replies appear in the trace as CONTEXT. Never label them. An expert that returns a wrong fact is not an orchestrator error by itself; what matters is what the orchestrator did with it.

# Read the whole trace first

Before you label any unit, read the entire trace from the question to the final answer, including every expert reply, the gold answer and the grader result. Write your reading in `trace_reading` first. Only then label the units, in order.

Judge each unit on what the orchestrator knew AT THAT POINT: the question, the roster, and the expert replies received so far. Never blame a unit for failing to know something it could not have known yet.

# Two roles: the orchestrator and you

- THE ORCHESTRATOR may answer from its own knowledge. Answering without calling an expert is a valid way to work and is not an error by itself.
- YOU, THE ANNOTATOR, must stay inside the dataset: the question, the trace, the expert replies, and the gold answers. Do not use your own world knowledge to decide that something the orchestrator or an expert said is true or false. If only outside knowledge would show a statement is wrong, treat it as not contradicted.

# How to use the gold answer

Use the gold answer for exactly two things:

1. To decide whether the final answer is correct (`answer_assessment`).
2. To check whether a fact the orchestrator stated FROM ITS OWN KNOWLEDGE is contradicted (rule 3).

Never use the gold answer to decide whether an EXPERT reply looked plausible. Judge an expert reply only as the orchestrator saw it: does it answer the sub-question, is it well-formed, does it conflict with anything already in the trace? A wrong expert answer that looks like a normal, responsive answer is plausible.

# The grader

`is_correct` comes from exact string matching and can be wrong. If the final answer means the same as a gold answer — plural vs singular, a possessive form ("Nike's" for "Nike"), the gold answer contained inside a longer sentence, or a close synonym ("automobile" for "car") — treat the answer as correct and set `answer_assessment` to `fuzzy_correct`. A trace whose outcome is correct can still contain errors, and a trace whose outcome is wrong does not have to contain an orchestrator error (the expert may be at fault).

# The label set

Each unit gets exactly ONE label from this list. The examples are invented to show the pattern; they are not from the traces you will see.

## Informational (no error)

The unit is a valid orchestrator step: its reasoning, sub-question, expert choice or answer is sound given what it knew at that point. Say why it is valid in `reason`.

## Theme: Task interpretation

**Goal misunderstanding.** The orchestrator incorrectly understands the intended outcome, target, or success criterion of the task — WHAT THE QUESTION ASKS. This may happen during initial planning, after receiving intermediate results, when deciding what remains to be done, or at any stage of the process. It covers a reversed relation, the wrong level of answer, and a misread entity (for example a misspelled name read as a different or fictional thing).
*Example:* asked "Which league did the club join in 1990?", the orchestrator treats the question as asking which country the club is in.

**Constraint loss.** The orchestrator omits, alters, weakens, or fails to propagate a condition that should constrain planning, delegation, evaluation, or completion. Constraints can include scope, budget, format, deadline, privacy, data source, compatibility, safety, or user preference.
*Example:* asked for "the first film he directed after 2000", the orchestrator asks the expert "What films did he direct?" and answers with his first film overall.

**Dependency loss.** The orchestrator fails to retain or use a prerequisite, ordering relation, or information link between task components. A constraint governs how work must be performed or what the result must satisfy; a dependency specifies what information or work must precede or inform another step.
*Example:* the question is "Where was the author of Book X born?". Round 1 finds the author is Jane Roe. Round 2 asks "Where was the author born?" without naming Jane Roe, or asks for the birthplace before the author is known.

## Theme: Coordination

**Wrong subtask generation.** The orchestrator creates a subtask that does not appropriately serve the current objective. The subtask may have the wrong target, relation, scope, level of detail, or expected output. This applies to both initial and follow-up subtasks. Use it when the orchestrator's reasoning has the right target but the sub-question it writes is badly formed.
*Example:* the reasoning correctly says it needs the year a bridge opened, but the sub-question asks "Who designed the bridge?".

**Wrong expert assignment.** The orchestrator selects an unsuitable agent, tool, data source, or processing route for a task, given the available alternatives and the information at the time. This concerns the orchestrator's selection, not whether the selected expert happens to make a mistake. Judge it against the roster only.
*Example:* a question about a football club's stadium is sent to the political-history expert while a sports expert and two general experts are available.

**Repeating coordination.** The orchestrator continues, retries, or returns to an approach despite evidence that it is unsuitable, without new information or a meaningful modification that justifies another attempt: the same question, the same route, or the same loop again, exhausting resources. Sending another sub-question to an expert that has just failed counts as Repeating coordination when that expert's domain is relevant to the question.
*Example:* Expert 3 fails with an error; the orchestrator sends the next sub-question of the same task to Expert 3 again although other relevant experts are available.

**Redundant work.** The orchestrator requests or performs work that duplicates existing work or is unnecessary for the task's current needs. The work is new in form (a reworded question, an extra call, an extra step) but is not fruitful. Subtypes: `duplicate delegation`, `duplicate request`, `unnecessary additional work`.
*Example:* the expert has already returned "1962" for the opening year; the orchestrator asks a second expert "In what year did it open?" with no stated doubt about the first answer.

## Theme: Progress management

**Unsupported belief.** The orchestrator forms, maintains, or acts on a proposition that is not adequately supported by the information available at that point. The belief need not be a factual answer: it may concern task status, agent capability, user intent, result quality, or whether an action succeeded. For facts stated from the orchestrator's own knowledge, see rule 3.
*Example:* without calling any expert, the orchestrator states "the river through that city is the Ohio" (false) and builds the answer on it.

**Information loss.** The orchestrator does not use the information provided to it properly: it wrongly reduces, filters out, or mis-weights available evidence, intermediate outputs, feedback, or system signals, WITHOUT stating a disagreement with it. Subtypes: `over-acceptance` (trusting evidence that is visibly weak — empty, off-topic, malformed, or conflicting with the trace), `under-weighting` (discounting relevant evidence without justification), `evidence override` (replacing stronger evidence with a less-supported alternative), `conflict mishandling` (resolving inconsistent evidence without adequate grounds).
*Example:* the expert answers "Real Madrid"; the final answer says "Barcelona" with no explanation.

**Verification failure.** The orchestrator's verification decision is poorly calibrated to the uncertainty, stakes, and evidence. The core case: the orchestrator receives an expert answer, STATES doubt or disagreement about it, and does not check it (no follow-up question, no second expert) before proceeding. Subtypes: `missed verification`, `insufficient verification`, `irrelevant verification`, `excessive verification`, `repeated verification`.
*Example:* the expert says the treaty was signed in 1815; the orchestrator writes "this seems wrong, I believe it was 1814" and answers 1814 without asking anyone.

**State-tracking failure.** The orchestrator incorrectly represents or loses track of the workflow state across attempts: what has been attempted, established, rejected, completed, or remains unresolved.
*Example:* round 2 establishes the actor's name; in round 4 the orchestrator says the actor is still unknown, or answers with a name that was rejected in round 3.

**Premature termination.** The orchestrator concludes that the task cannot be answered, that the question's premise is false, or that no answer exists, and stops, while reasonable options remain (another relevant expert, a reworded sub-question, a follow-up). Always put this label on the `final_answer` unit, because that is where the orchestrator stops; a round whose reasoning reaches the same conclusion is `Informational` (it is carried into the final answer).
*Example:* after one expert fails, the orchestrator answers "The information is not available" although four relevant experts were never asked.

## OTHER (strict)

Use `OTHER` ONLY when the unit clearly contains an orchestrator error AND none of the twelve concepts above describes it, even loosely. It is not a place for uncertainty between two concepts. If you use it, fill `other_proposal` with a short new concept name, a one-sentence definition written in the same style as the concepts above, and the reason each nearby concept does not fit.

# Decision rules

Apply these rules so that two annotators reach the same label.

1. **One label per unit.** Pick the single concept that best describes the unit's main fault. Fill `second_label` ONLY when two concepts fit exactly equally and the rules below do not separate them. If you can say which of the two is primary, it is not a tie: set `second_label` to null.

2. **Label the fault where it is committed.** A unit gets an error label for a new fault it makes. A later unit that only carries forward an earlier fault, without a new fault of its own, is `Informational`; name the earlier unit in the reason. A decision to stop because the task is judged unanswerable is a new fault (Premature termination) on `final_answer`, even when it follows from an earlier error. A round only gets an error label when its OWN action is faulty: a reasoning turn that holds a doubtful thought but still sends a sound, neutral sub-question is `Informational`. A round that says it still needs information but sends no sub-question is `Informational`; the fault shows at `final_answer`, where the orchestrator answers without that information.

3. **Facts from the orchestrator's own knowledge.** When the orchestrator states a fact from its own knowledge (no expert reply supports it) and acts on it — to plan, to shape a sub-question, to decide not to delegate, to stop, or as the answer — label Unsupported belief if EITHER:
   - (a) the fact is CONTRADICTED by the gold answer or by another part of the trace (for example an expert reply). A fact is not contradicted just because it uses different words from the gold answer ("large house" vs "big house" is the same meaning). Do not use outside knowledge to decide this. A contradiction may be derived by combining parts of the dataset — for example, in a multi-hop question the gold answer names the director's spouse and an expert reply gives a different spouse for the director the orchestrator assumed, so the assumed director is contradicted. OR
   - (b) the orchestrator itself signals it is unsure, and then uses the fact without calling an expert. Read the unit's reasoning for hedges such as: "I need to verify", "I need to confirm", "to be certain", "likely", "probably", "it seems", "may", "might", "possibly", "I am not sure", "could refer to". A hedge counts even if the orchestrator later sounds confident in the same turn.
   Otherwise — the fact is not contradicted and not hedged — the unit is `Informational`, and answering without an expert is valid.

4. **Accepting an expert answer.** When a suitable expert returns an answer that is responsive and well-formed, and nothing in the trace so far conflicts with it, accepting it without a check is `Informational` — even if the answer is wrong. The expert is at fault, not the orchestrator. Do not use the gold answer to call such a reply implausible.

5. **Stated doubt goes to Verification failure.** If the orchestrator states doubt or disagreement about an expert answer and then proceeds without checking — whether it keeps the answer, drops it, or replaces it with its own belief — label Verification failure. Use Information loss only when there is no stated disagreement: the evidence is simply dropped, mis-read, mis-weighted, or visibly weak evidence is trusted.
   A CHECK means a new sub-question that could show the answer wrong: sent to a different expert, or a neutral question to the same expert. A leading re-question to the same expert that presumes the answer, or the orchestrator's own "further reflection", is not a check.
   *Negative example:* the expert says "Composer A"; the orchestrator writes "this contradicts what I know, it was Composer B" and answers from that. This is Verification failure (missed verification), NOT Information loss / evidence override — the disagreement is stated.

6. **Goal misunderstanding vs Wrong subtask generation vs Unsupported belief.**
   - The reasoning states the wrong target (what the question asks) → Goal misunderstanding.
   - The reasoning has the right target, but the sub-question is badly formed → Wrong subtask generation.
   - The orchestrator understands what is asked but fills in a wrong fact from its own knowledge → Unsupported belief.

7. **Dependency loss vs Wrong subtask generation.** If a sub-question omits an entity or result that it needs from an earlier step or from the question's chain of links, label Dependency loss. If it keeps the links but asks for the wrong thing, label Wrong subtask generation.

8. **Repeating coordination vs Redundant work vs Wrong expert assignment.**
   - The same approach again after evidence it does not work, with no new information — including a new sub-question to an expert that has just failed when its domain is relevant → Repeating coordination.
   - A different action that is unnecessary or duplicates what is already established → Redundant work.
   - An expert that is clearly unsuitable for the sub-question given the roster, while a clearly better option exists → Wrong expert assignment. Several experts can be reasonable for one question; Experts 1 and 7 are general-purpose and suit most factual questions.

9. **Order of precedence on `final_answer`.** Check in this order and take the first that applies:
   1. Verification failure — only if the `final_answer` unit itself states doubt about an expert answer and answers without checking.
   2. Premature termination — the final answer says the task cannot be answered, the premise is false, or no answer exists, while options remained.
   3. Any other concept, or `Informational`.

10. **Dependency loss vs State-tracking failure.** Dependency loss: a link between task components is broken. State-tracking failure: across multiple attempts, the orchestrator loses or misrecords what it has already tried, found, or rejected.

11. **Constraint loss vs Wrong subtask generation (scope).** A condition that the QUESTION states and the sub-question drops or changes (a date, a place, "first", "after 2000") → Constraint loss. A narrowing or extra condition that the orchestrator ADDS on its own → Wrong subtask generation.

# Severity

Every unit also gets a `severity`. The concept says WHAT went wrong; the severity says HOW MUCH it mattered to the outcome.

- `Informational` — no fault. A unit is `Informational` in severity if and only if its label is `Informational`.
- `Critical` — the root cause of a wrong final answer.
- `Error` — a real fault that contributes to the outcome, or that the answer rests on, but is not the root cause.
- `Warning` — a fault that only wastes effort or adds risk and does not change the path to the answer (for example a duplicate call, or an unnecessary check).

Rules, applied in order:

S1. **Correct traces have no Critical.** If `answer_assessment` is `correct` or `fuzzy_correct`, every error unit is `Error` or `Warning`. Use `Error` when the answer rests on the fault (an unsupported or hedged belief that the answer uses, a doubt that was not checked); use `Warning` when the fault only cost effort (Redundant work, Repeating coordination, excessive or repeated verification).

S2. **Failed traces.** If `answer_assessment` is `incorrect` and at least one unit has an error label, exactly one unit is `Critical` — or two, only under S4. If no unit has an error label (for example the expert returned a plausible wrong answer), no unit is `Critical`.

S3. **Which unit is Critical.** Take the error units in order. The Critical unit is the EARLIEST fault that the wrong final answer follows from: had that unit been done correctly, the orchestrator's path could have reached the gold answer. Later faults on the same chain are `Error`. Faults that only cost effort are `Warning`.
   *Example:* round 2 retries a failed expert (Repeating coordination) and the final answer gives up (Premature termination). Round 2 is Critical; the final answer is Error.

S4. **Two Critical units** only when there are two faults on SEPARATE chains, each of which on its own would have made the final answer wrong (for example two independent hops of a multi-hop question, each filled with a contradicted belief). Explain why in `root_cause.why`.

# Checks you fill before the label

For each unit, fill these fields FIRST, by quoting the trace; then choose the label and severity. Quotes must be copied exactly from the trace text you were given (the code checks this).

- `hedge_quote` — the exact hedge in THIS unit's reasoning (rule 3b), or null.
- `own_fact_quote` — the exact words of a fact the orchestrator states from its own knowledge and acts on in this unit, or null.
- `contradicted_by` — if `own_fact_quote` is set and is contradicted (rule 3a): the exact gold answer or expert reply text that contradicts it; otherwise null. Never write outside knowledge here.
- `unchecked_doubt_quote` — the exact words in THIS unit where the orchestrator states doubt or disagreement about an expert reply and then does NOT check it (rule 5), or null. If the unit checks (a new sub-question to a different expert, or a neutral one), set null.
- `repeats_fault_from` — the step_key of an earlier unit if this unit only carries that unit's fault forward (rule 2), or null.
- `declares_no_answer` — true only on `final_answer`, when the final answer says the task cannot be answered, the premise is false, or no answer exists.

The code enforces these consequences, so keep them consistent:
- `repeats_fault_from` set → label `Informational`.
- `unchecked_doubt_quote` set → label Verification failure.
- `declares_no_answer` true and no `unchecked_doubt_quote` → label Premature termination.
- Label Unsupported belief → `hedge_quote` or `contradicted_by` set.

# Fields

- `trace_reading`: 2–5 sentences. What the question asks, what the orchestrator did round by round, what the experts returned, and why the trace ended as it did.
- `answer_assessment`: `correct`, `fuzzy_correct` or `incorrect`, judged by you against the gold answers.
- `trace_valid`: false only if the trace is malformed or cannot be judged (for example the question itself is broken). Give the reason in `trace_valid_reason`.
- `root_cause`: `{"step_keys": [...], "why": "..."}` — the step_keys of the Critical units (empty when there is none) and one or two sentences on why (rules S2–S4).
- For each unit: `step_key`, the six check fields above, `label`, `severity`, `subtype` (only for Redundant work, Information loss and Verification failure; otherwise null), `evidence` (a short exact quote from that unit that shows the fault or the soundness), `reason` (1–3 sentences, specific to this trace, naming the rule you applied when a rule decided the label), `second_label`, `other_proposal`.

Label every orchestrator unit listed in the trace, exactly once, in order. Record your answer by calling the `record_annotation` tool.
