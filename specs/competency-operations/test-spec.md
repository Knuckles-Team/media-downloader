# CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001` | `tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields` (planned) | The operation returns the documented fields. |

## Negative and boundary cases

Each proving test above includes the refusal or error case that its row names. A vendor outage or an unauthorised call must return the SDK typed error.

## Quality and release proof

Run `uv run pytest tests` and `pre-commit run --all-files` from the repository root. A planned test is added by the code change that lands the row.
