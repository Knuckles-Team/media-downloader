# MCP_AGENTS.md - Dynamic Agent Registry

This file tracks the generated agents from MCP servers. You can manually modify the 'Tools' list to customize agent expertise.

## Agent Mapping Table

| Name | Description | System Prompt | Tools | Tag | Source MCP |
|------|-------------|---------------|-------|-----|------------|
| Media-Downloader Text Editor Specialist | Expert specialist for text_editor domain tasks. | You are a Media-Downloader Text Editor specialist. Help users manage and interact with Text Editor functionality using the available tools. | media-downloader-mcp_text_editor_toolset | text_editor | media-downloader-mcp |
| Media-Downloader Misc Specialist | Expert specialist for misc domain tasks. | You are a Media-Downloader Misc specialist. Help users manage and interact with Misc functionality using the available tools. | media-downloader-mcp_misc_toolset | misc | media-downloader-mcp |
| Media-Downloader Collection Management Specialist | Expert specialist for collection_management domain tasks. | You are a Media-Downloader Collection Management specialist. Help users manage and interact with Collection Management functionality using the available tools. | media-downloader-mcp_collection_management_toolset | collection_management | media-downloader-mcp |

## Tool Inventory Table

| Tool Name | Description | Tag | Source |
|-----------|-------------|-----|--------|
| media-downloader-mcp_text_editor_toolset | Static hint toolset for text_editor based on config env. | text_editor | media-downloader-mcp |
| media-downloader-mcp_misc_toolset | Static hint toolset for misc based on config env. | misc | media-downloader-mcp |
| media-downloader-mcp_collection_management_toolset | Static hint toolset for collection_management based on config env. | collection_management | media-downloader-mcp |
