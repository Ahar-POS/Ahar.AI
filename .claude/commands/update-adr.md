# Update ADR

You are maintaining the Architecture Decision Records (ADRs) for Ahar.AI.
ADRs live in `docs/adr/`. The index is `docs/README.md`.

ADRs capture *why* the team made significant technical decisions — model choices,
data strategies, infrastructure, architecture, and feature design. They are the
audit trail of the system's thinking.

---

## Step 1 — Read the existing ADRs

Read every file in `docs/adr/`. Know what is already recorded before touching anything.

---

## Step 2 — Understand what changed

Look at:
- The current conversation context — what decisions were just discussed or made
- `git log --oneline -20` — recent commits that imply decisions
- `git diff HEAD` — code changes that haven't been recorded yet
- `docs/features/` — pending features that may have just been resolved

---

## Step 3 — Decide: update or create?

**Update an existing ADR when:**
- A recorded decision has been reversed, refined, or superseded
- New results are available for something already documented
- A "Deferred" item has now been implemented
- A "Known Limitation" has been resolved
- The status needs changing (Draft → Accepted, Accepted → Superseded)

**Create a new ADR when:**
- A genuinely new technical area is being decided (new model, new service, new data source, new architecture pattern, new infrastructure choice)
- The scope is distinct enough that cramming it into an existing ADR would obscure the reasoning

**Do nothing when:**
- The change is purely implementation detail already obvious from the code
- It's a bug fix with no design decision behind it
- The user didn't make any decision — they just asked a question

---

## Step 4 — ADR filename and numbering

- Check the highest existing number in `docs/adr/`
- New files: `ADR-NNN-short-kebab-case-title.md`
- Examples: `ADR-002-multi-restaurant-model-strategy.md`, `ADR-003-chatbot-agent-architecture.md`

---

## Step 5 — Write or update using this structure

```markdown
# ADR-NNN: Short Title

**Date**: YYYY-MM-DD  (use today's actual date — never "today" or "recently")
**Status**: Draft | Accepted | Superseded by ADR-NNN
**Decider**: <name or "team">
**Context**: <one sentence — what part of the system this covers>

---

## Problem
What decision needed to be made and why it mattered.

## Decisions Made

### Decision: <title>
- **Chosen**: what was picked
- **Rejected**: alternatives considered and why they lost
- **Reason**: the core reasoning — this is the most important part

(one block per decision)

## Decisions Rejected / Deferred

### Rejected: <title>
- **Reason**: why ruled out permanently

### Deferred: <title>
- **Reason**: why not now, and what condition would trigger revisiting it

## Known Limitations
| Issue | Impact | Path forward |
|---|---|---|

## Output / Affected Files
| File or service | What changed or was created |
|---|---|

## Next Decisions Pending
Numbered list of open questions that will eventually need their own ADR entries.
```

---

## Step 6 — Update `docs/README.md`

If a new ADR was created, add a row to the Decision Records table:
```
| [ADR-NNN](adr/ADR-NNN-title.md) | Short title | Draft/Accepted |
```

If an existing ADR's status changed, update its row.

---

## Step 7 — Report back to the user

Tell them:
- Which ADR(s) you updated or created and why
- A 3-bullet plain-English summary of what was recorded
- Any open decisions you spotted that should be tracked in a future ADR

---

## Hard rules

- **Never delete content from an existing ADR.** Mark old decisions as superseded with a note inline.
- **Record the why, not just the what.** The code shows what was done. The ADR explains why.
- **One decision per `### Decision:` block.** Don't bundle multiple choices under one heading.
- **Dates must be absolute.** Use the current date from the system context.
- **Don't invent decisions.** Only record what was actually discussed or decided in this session.
- **Domain is all of Ahar.AI** — forecasting, chatbot, agents, auth, multi-tenancy, deployment, data pipelines, anything.
