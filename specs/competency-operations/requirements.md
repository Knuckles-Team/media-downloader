# CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001` | The connector must serve a `list_downloads` operation that returns job id, source URL, status, error, completedAt and output path for each download. Caller chain: arbora `fleet.call` reaches a new `list_downloads` tool registered in `media_downloader/mcp_server.py`, which reads the job records of `MediaDownloader` (`media_downloader/media_downloader.py`). Shape: a read-only `list_downloads` tool in `media_downloader/mcp_server.py` returning job id, source URL, status, error, completedAt and output path per download; reuses the existing job state of `MediaDownloader`. Proving test (planned): `tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields`. Proving test (planned): `tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields`. Proving test (planned): `tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields`. | The operation returns the documented fields. |
