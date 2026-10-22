# CONN-MEDIA-DOWNLOADER — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Existing system and reuse

The SDK tool surface registers each public `MediaDownloader` method as a tool. The tool result is the method return value.

## Architecture

`get_channel_videos` tries each channel URL form. `_append_links` queues the links on `self.links` and returns the queued links. `get_channel_videos` returns that list.

## Interfaces and data model

The tool returns a list of video URLs. The `channel` and `limit` arguments do not change.

## Live integration path

The fleet gateway calls `media_downloader_get_channel_videos`. The SDK tool surface builds a client with `get_client` and returns the method result.

## Quality and release gates

The focused tests run with `pytest -q`. A merge to the default branch publishes the package and the image.

## Risks, alternatives, and decisions

The method returned no value before, so the tool returned empty content. Each tool call builds a new client, so the return value is the only result channel.
