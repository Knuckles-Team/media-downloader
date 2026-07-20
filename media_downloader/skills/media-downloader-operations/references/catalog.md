# Provider workflow catalog

Load only the workflow relevant to the current request.

- [media-audio](../../media-audio/WORKFLOW.md): Extract audio as MP3 from a video/media URL via the media-downloader MCP server, natively storing the resulting audio into epistemic-graph as a content-addressed blob + :MediaAsset. Use when the agent needs the audio track (podcast, music, lecture) rather than the full video. Do NOT use for full-video download (media-download) or for transcription (use the audio-transcriber package).
- [media-download](../../media-download/WORKFLOW.md): Download video (or audio) from YouTube, Rumble, and other yt-dlp-supported sites via the media-downloader MCP server, and natively store the downloaded media into the epistemic-graph knowledge graph as a content-addressed blob + :MediaAsset. Use when the agent must fetch a video by URL and optionally persist the raw bytes + metadata into the KG. Do NOT use for audio-only extraction to MP3 (media-audio) or for querying already-ingested media (query the KG :MediaAsset nodes directly).
