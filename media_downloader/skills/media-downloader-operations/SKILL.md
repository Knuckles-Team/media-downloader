---
name: media-downloader-operations
skill_type: skill
description: >-
  Operate media-downloader through its governed MCP and Arbora capabilities, including media audio, media download, media watch. Use when a request requires this provider's read, change, automation, ingestion, troubleshooting, or evidence workflows.
---

# Media Downloader Operations

Use the provider's governed MCP tools through Arbora delegation.

## Workflow

1. Establish the verified GraphSession and tenant before discovery or retrieval.
2. Discover the current condensed tool surface; never assume a stale tool name or schema.
3. Prefer read-only inspection first. For changes, present impact and use the provider's
   dry-run or preview mode when available.
4. Execute mutations as fenced WorkItems so retries remain idempotent and auditable.
5. Ingest source data only through the signed connector preset and ChangeEnvelope path.
6. Verify the durable result and its trace/evidence before reporting completion.

## Steps

1. Establish the verified GraphSession and tenant, and verify both are present before the first `find` call.
2. Discover the current tool surface with `find` and verify the exact action schema before building arguments.
3. Run read-only inspection first, such as `list_watch_skills`, and verify the result describes the intended items.
4. For a change, present the impact and use the provider dry-run or the `act` preview when offered, and verify the preview matches the request.
5. Execute the mutation as a fenced WorkItem with `act`, and verify the returned trace or evidence reference shows the durable result.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| A tool name or parameter is rejected | The cached tool surface is stale | Run `find` for the intent again and use the returned schema |
| A mutation is denied by policy | An approval or ACL gate is closed | Report the denial and stop, because a policy denial is final |
| A download is refused for a host | The URL points at a private host | Use a public URL, because private hosts are allowed only through the administrator's exact-host list |

## Safety contract

- Never persist credentials, endpoints, raw personal identifiers, hostnames, or local paths.
- Resolve TLS trust and verification from environment/configuration; never hardcode bypasses.
- Treat unknown ACL, tenant, schema, or tool-contract state as a hard failure.
- Require explicit approval for destructive, externally visible, or irreversible actions.
- Keep runtime traces policy-scoped and privacy-sanitized.

## Specialized workflows

Read [the workflow catalog](references/catalog.md) only when the request needs a
provider-specific procedure, parameter map, script, or reference asset.
