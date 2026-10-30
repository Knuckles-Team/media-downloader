# CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001` | The connector must serve a `list_downloads` operation that returns job id, source URL, status, error, completedAt and output path for each download. Proving test: `tests/test_list_downloads.py`. | The operation returns the documented fields. |
