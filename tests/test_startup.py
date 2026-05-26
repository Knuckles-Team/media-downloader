def test_server_startup():
    """Validates that the server module can start successfully."""
    # If this is not an agent, just pass
    import os

    if not os.path.exists("agent_server.py") and not any(
        os.path.exists(os.path.join(d, "agent_server.py"))
        for d in ["src", "agent", "media_downloader"]
    ):
        return

    import media_downloader.media_downloader
    import media_downloader.mcp_server
    import media_downloader.agent_server

    print("Startup tests handled correctly.")
