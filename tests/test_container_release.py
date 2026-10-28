"""The released-wheel image refresh uses the shared public payload guard."""

from pathlib import Path

import yaml


def test_public_wheel_preflight_precedes_container_publication():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load(
        (root / ".github/workflows/container-release.yml").read_text()
    )
    jobs = workflow["jobs"]
    steps = jobs["verify-public-wheel"]["steps"]
    guard = next(
        step
        for step in steps
        if step.get("uses", "").endswith("/verify-release-version")
    )
    assert guard["with"] == {
        "mode": "published-wheel",
        "distribution": "media-downloader",
        "module": "media_downloader",
    }
    assert jobs["publish-docker"]["needs"] == "verify-public-wheel"
    assert (
        jobs["publish-docker"]["uses"]
        == "Knuckles-Team/pipelines/.github/workflows/container_pipeline.yml@main"
    )
