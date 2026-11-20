# Menschheit Arena

Two pillars, one local start: a multi-agent debate arena (pro humanity versus contra humanity) and Sentinel Lab, a pentest control plane with scope enforcement and human-in-the-loop.

The app runs without any API key in deterministic demo mode. Only once model names and a key are configured do real LLM requests leave the machine.

Full English documentation: [docs/README.en.md](docs/README.en.md)

```
menschheit demo    # full debate, no key
menschheit serve   # http://127.0.0.1:8000
```