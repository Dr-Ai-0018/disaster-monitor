# Workflow Stage Testing

Use `tests/workflow_stage_tester.py` to verify each stage separately.

## Examples

```bash
python tests/workflow_stage_tester.py inspect --uuid <UUID>
python tests/workflow_stage_tester.py quality --uuid <UUID>
python tests/workflow_stage_tester.py inference --uuid <UUID>
python tests/workflow_stage_tester.py summary --uuid <UUID>
python tests/workflow_stage_tester.py report --date 2026-03-31
python tests/workflow_stage_tester.py all --uuid <UUID> --date 2026-03-31
```

## What Each Command Checks

- `inspect`: event, image path existence, queue item, product presence
- `quality`: AI quality assessment on the current event's pre/post imagery
- `inference`: only consumes the specified UUID from the internal inference queue
- `summary`: generates a single event summary from an existing product
- `report`: generates a daily report for the given date
- `all`: runs the above in sequence

## Notes

- `quality` requires both `pre` and `post` imagery.
- `summary` requires an existing product row.
- `report` uses the same report generation code path as production.
- `summary --persist` writes the generated summary back to the database.
