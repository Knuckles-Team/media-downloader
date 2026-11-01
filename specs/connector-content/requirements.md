# CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT-R001` | **Default content.** `pyproject.toml` declares `media-downloader-mcp` as the single `scion_sdk.connector` entry point. The server lists the packaged `skill://` and `ontology://` resources and the packaged prompts with no `content=` argument. Caller chain: `media-downloader` in `pyproject.toml` runs `media_downloader.media_downloader:media_downloader`, which builds the server from the `scion_sdk.connector` entry point `media_downloader:connector` (`media_downloader/__init__.py:98`); the SDK `Connector` then lists the packaged skills, ontology and prompts. Shape: `pyproject.toml` entry point `media-downloader-mcp` plus the `connector = Connector(.)` object in `media_downloader/__init__.py`; the packaged `skills/`, `ontology/` and `prompts/` directories of `media_downloader` are reused as is, with no connector-local registration code. Proving test: `tests/test_default_content_surfaces.py::test_default_content_surfaces`. | `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt. |
