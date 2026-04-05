---
phase: 15-notion-ingestion
status: Incomplete
services:
  - notion
---

# Phase 15: Notion Ingestion - User Setup

## Notion Integration

### Environment / Config

| Variable | Where | How to get |
|----------|-------|------------|
| `notion.token` | `config/config.yaml` | Notion Settings -> My connections -> Develop or manage integrations -> Create new integration -> Copy Internal Integration Secret |

### Account Setup

- [ ] Create a Notion internal integration at https://www.notion.so/my-integrations
- [ ] Copy the Internal Integration Secret
- [ ] Add `notion.token` and `notion.enabled: true` to `config/config.yaml`

### Dashboard Configuration

- [ ] Share each Notion page/database with your integration: open page/database -> ... menu -> Add connections -> select your integration
- [ ] Run `python -m src.main discover-notion` to select databases to watch for all-changes tracking

### Verification

```bash
# Verify config loads
python -c "from src.config import load_config; c = load_config(); print(f'Notion enabled: {c.notion.enabled}, token set: {bool(c.notion.token)}')"

# Discover databases
python -m src.main discover-notion

# Run pipeline with Notion
python -m src.main run --date yesterday
```

---
*Phase: 15-notion-ingestion*
*Generated: 2026-04-05*
