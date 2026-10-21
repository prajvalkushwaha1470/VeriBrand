# VeriBrand MVP — CodeAxis Round 2

A functional brand-governance MVP based on the Single Thread Round 1 plan. It includes a responsive dashboard, brand-kit facts, deterministic content checks, explainable findings, human decisions, review status and review history.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs

## What works

- Synthetic Lumio brand kit preloaded with price, tone and terminology facts.
- Add/remove approved facts and see source titles.
- Submit a draft and run deterministic checks for unsupported superlatives, incorrect configured price, stacked exclamation marks and hype-heavy wording.
- Findings show severity, reason, source, confidence and suggested fix.
- Accept, edit/note or dismiss individual findings.
- Approve a draft or request changes; decisions are stored in SQLite.
- Review history and dashboard metrics.
- Responsive UI and FastAPI endpoints.

## Honest limitations

This build intentionally uses transparent rule-based checks and does not call an external LLM. The current checks are not a complete semantic brand audit; no finding does not guarantee compliance. The “Edit / note” action records the note in the audit log but does not automatically rewrite the draft. Login/role-based permissions, DOCX parsing, PDF/image review, embeddings/RAG, production-grade multi-user auth and cloud deployment still need implementation/validation before claiming them. SQLite is used for a low-friction demo; replace with managed PostgreSQL for production.

## Deploy

Deploy as a Python web service with build/install command `pip install -r requirements.txt` and start command `uvicorn backend_main:app --host 0.0.0.0 --port $PORT`. Set a persistent disk for `veribrand.db` if your host's filesystem is ephemeral. Before submission, test the public URL in an incognito browser and ensure no sign-in is required.

## Team

Single Thread — Prashant Kumar Yadav, Pranjal Gupta, Prajval Kushwaha.
