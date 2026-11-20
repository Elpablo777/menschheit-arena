# Menschheit Arena (English)

Two pillars, one local start: a multi-agent debate arena and a pentest control plane that plans but never executes.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

menschheit demo      # full deterministic debate, no API key
menschheit serve     # http://127.0.0.1:8000
```

`menschheit setup` writes a `.env` after backing up any existing one. `menschheit doctor` checks configuration, prompt resources, UI files, database and the audit chain.

## Debate arena

Pro and contra each get an isolated opening prompt. Every turn must begin with a steelman of the opposing side; the private scratchpad is stored but never shown to the opponent. A moderator scores each round and can flag sycophancy or drift. Its "convinced" verdict is only honoured when at least one side drops its confidence to 25 or below — that gate is enforced in code, not in the model. The judge scores in both orders (A/B and B/A) and publishes the difference as position bias. Surviving claims, refuted claims and open constitutional conflicts are separated.

Stop reasons are `CONVINCED`, `SYNTHESIS_REACHED` and `DEADLOCK`. There is no silent agreement.

## Sentinel Lab

- Scope guard: IP, CIDR, domain, URL, port allowlist. Public targets blocked by default, global wildcards and credentials in URLs rejected.
- Actions are proposals, split into `READ_ONLY` and `ACTIVE_REQUIRES_APPROVAL`. Nothing runs.
- Approvals need a full name and a timestamp; both are written to the audit log.
- Findings only appear in reports after a human verification checkbox.
- The RoE text is stored as SHA-256; the audit chain is append-only (SQLite triggers plus hash chaining over `seq`).
- The kill switch rejects all open and approved actions and blocks further planning.

`PENTEST_EXECUTION_ENABLED=false` and `ALLOW_PUBLIC_TARGETS=false` ship by default and are not implemented for execution.

## Configuration

All values live in `.env.example`. The LLM layer speaks OpenAI-compatible `/chat/completions`. Presets: `mock`, `openrouter`, `deepseek`, `openai`, `mistral`, `ollama`, `litellm`, `openai_compat`.

## Language

German by default, fully switchable to English — UI, prompts, knowledge base, reports. The switch is in the header.

## Tests

```bash
pytest -q
ruff check src tests
menschheit doctor
```

Coverage: i18n parity, JSON parsing and aliases, confidence coercion, judge score recomputation, scope guard, full API flow including token middleware, audit chain and append-only triggers.

## Security posture

No offensive execution, no payloads, no exfiltration. The host runs no scans against third parties. Before any real engagement: written RoE, named approver, emergency contact, scope list, retention concept, data processing agreement with the model provider, EU AI Act transparency review. The templates in `legal/` are starting points, not legal advice.

## License

MIT. Model providers keep their own terms.