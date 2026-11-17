# Annotrace

A workbench for step-level human and LLM annotation of agent traces.

Load agent traces from several frameworks, write your own codebook (or have a model draft one from a sample of your traces), label each step, have a model answer the same questions, and measure how far any two annotators agree, human or model.

Companion code for *Annotrace: A Workbench for Step-Level Human and LLM Annotation of Agent Traces* (The Web Conference 2027, demonstration track).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd annotrace && streamlit run app.py
```

Open http://localhost:8501. The sidebar walks through five screens:

| Screen | Does |
|---|---|
| Traces | Load a file and see how its runs break into steps, before labelling anything |
| Questions | Write your questions and labels, or have a model draft them from a one-line goal |
| Annotate | Label each step; ask a model to answer the steps you have not |
| Review | Read the work back; export JSON (with the questions) or CSV |
| Compare | Raw agreement, Cohen's kappa, the commonest confusions and every disputed step, between any two annotation sets |

## Trace formats

The format is detected from the file's content.

| Adapter | Reads |
|---|---|
| `otel_genai` | OpenTelemetry OTLP JSON with GenAI conventions, and OpenInference span exports (Arize Phoenix, Patronus, TRAIL) |
| `langsmith` | LangSmith run exports |
| `langfuse` | Langfuse exports |
| `chat_messages` | Role/content message lists, including tool calls (tau-bench) and multi-agent logs whose roles are agent names (Magentic-One, AgentRx) |
| `who_and_when` | Who&When failure cases |
| `coordinator` | Coordinator-and-worker runs, with Thinking-Action-Response cycles recovered from a worker's tagged reasoning |

`annotrace/samples/` has one small example per format. `annotrace/schemas/` has example codebooks, including one for auditing an agent acting for a user.

## Models

Model features (drafting a codebook, answering steps) are optional. Two back-ends:

- **Amazon Bedrock** (default), with your own AWS credentials: `pip install boto3`, then set `AWS_PROFILE` and `AWS_REGION` as for any boto3 client. Your account needs access to the model you pick.
- **A hosted gateway** that accepts `{"model", "max_tokens", "messages"}`: set `ANNOTRACE_GATEWAY_URL` and `ANNOTRACE_API_KEY`.

Settings can also go in a `.env` file at the repository root. It is gitignored.

When a model is asked, the text of the steps being annotated is sent to that model's provider. Annotate traces that contain personal or confidential data without model assistance.

## Evaluation

`evaluation/` holds everything behind the numbers in the paper.

| Path | Contents |
|---|---|
| `labels/human_labels_final.json` | The released human label set for the 40-run coordinator corpus (348 steps) |
| `labels/annotator_{a,b}_first_pass.json` | The two annotators' independent first passes |
| `annotation_handbook.md` | The codebook the annotators followed, also given to the models as house rules |
| `results/model_runs/` | Raw output of six models (Bedrock) on the 40 runs |
| `results/annotrace_exports/` | The human labels and each model's answers as Annotrace exports; open any two in Compare |
| `results/agreement_scores.txt` | Every agreement figure in the paper |
| `results/adapter_validation.txt` | Adapter checks on public TRAIL, tau-bench, Who&When and AgentRx releases |
| `results/codebook_drafts.json` | Codebook drafts from five different samples, for the stability check |

Scripts take the repository root as their first argument:

```bash
python evaluation/score.py . evaluation/results/model_runs             # agreement figures
python evaluation/validate_adapters.py . <dir with trail/, ww/, agentrx/>  # adapter checks
python evaluation/run_models.py . <out dir> <bedrock model ids, comma-separated>
```

`run_models.py` and `to_annotrace_exports.py` need the 40 coordinator runs (`subset_40_stratified.jsonl`) in `evaluation/data/`. They come from the `Bin-Wu/Agent_Trajectory` dataset on Hugging Face, which is gated. The public trace sets come from:

- TRAIL: github.com/patronus-ai/trail-benchmark
- Who&When: huggingface.co/datasets/Kevin355/Who_and_When
- AgentRx: github.com/microsoft/agentrx

## Licence

MIT. See `LICENSE`.
