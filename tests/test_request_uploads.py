from __future__ import annotations

import io
from pathlib import Path

from engine.pipeline_runner import PipelineRunner, create_api_app


def make_client(tmp_path: Path):
    (tmp_path / "agents").mkdir(parents=True, exist_ok=True)
    runner = PipelineRunner(str(tmp_path))
    app = create_api_app(runner)
    app.config["TESTING"] = True
    return app.test_client()


def test_submit_text_request_still_works(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/requests",
        json={"title": "Text only", "text": "Ship the dashboard update", "source": "web"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["title"] == "Text only"
    assert payload["request_text"] == "Ship the dashboard update"
    assert payload["attachments"] == []


def test_submit_request_with_upload_persists_attachment(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/requests",
        data={
            "title": "Upload request",
            "text": "Please use the attached notes",
            "source": "web",
            "files": (io.BytesIO(b"line-1\nline-2\n"), "notes.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["source_metadata"]["attachment_count"] == 1
    assert len(payload["attachments"]) == 1

    attachment = payload["attachments"][0]
    assert attachment["name"] == "notes.txt"
    assert attachment["preview_available"] is True
    assert "line-1" in attachment["preview"]
    assert Path(attachment["path"]).exists()
    assert "request_uploads" in payload["artifacts"]