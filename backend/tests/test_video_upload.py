from pathlib import Path

from backend.app.api.v1 import photographers


def test_video_upload_uses_custom_cover(
    client,
    photographer_headers,
    monkeypatch,
    tmp_path,
):
    calls = {}
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")

    async def fake_save_video_file(upload_file, sub_dir="videos"):
        calls["video"] = (upload_file.filename, sub_dir)
        return "/static/videos/clip.mp4", str(video_path)

    async def fake_save_upload_file(upload_file, sub_dir="portfolios"):
        calls["cover"] = (upload_file.filename, sub_dir)
        return "/static/videos/covers/custom-cover.jpg"

    def fail_generate_thumbnail(*_args, **_kwargs):
        raise AssertionError("custom cover should skip frame extraction")

    monkeypatch.setattr(photographers, "save_video_file", fake_save_video_file)
    monkeypatch.setattr(photographers, "save_upload_file", fake_save_upload_file)
    monkeypatch.setattr(photographers, "generate_video_thumbnail", fail_generate_thumbnail)
    monkeypatch.setattr(photographers, "get_video_duration_seconds", lambda _path: 2.5)
    monkeypatch.setattr(photographers, "compress_video", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(photographers, "refresh_ai_resource_documents_for_user", lambda *_args, **_kwargs: None)

    response = client.post(
        "/api/v1/photographers/video/upload",
        headers=photographer_headers,
        data={"title": "Video Work", "compress": "false"},
        files={
            "file": ("clip.mp4", b"video", "video/mp4"),
            "cover": ("cover.jpg", b"cover", "image/jpeg"),
        },
    )

    assert response.status_code == 200, response.text
    work = response.json()["work"]
    assert work["thumbnail_url"] == "/static/videos/covers/custom-cover.jpg"
    assert calls["cover"] == ("cover.jpg", "videos/covers")
    assert calls["video"] == ("clip.mp4", "videos")


def test_video_upload_generates_frame_30_cover_when_no_custom_cover(
    client,
    photographer_headers,
    monkeypatch,
    tmp_path,
):
    calls = {}
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    thumb_path = tmp_path / "covers" / "clip_thumb.jpg"

    async def fake_save_video_file(upload_file, sub_dir="videos"):
        return "/static/videos/clip.mp4", str(video_path)

    def fake_generate_thumbnail(input_path, output_dir, frame_number=30):
        calls["generated"] = (input_path, output_dir, frame_number)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.write_bytes(b"thumb")
        return str(thumb_path)

    async def fake_save_local_file_to_storage(source_path, sub_dir, filename=None, content_type=None):
        calls["stored"] = (source_path, sub_dir, filename, content_type)
        return "/static/videos/covers/generated-thumb.jpg"

    async def fail_save_upload_file(*_args, **_kwargs):
        raise AssertionError("no custom cover should not save uploaded cover")

    monkeypatch.setattr(photographers, "save_video_file", fake_save_video_file)
    monkeypatch.setattr(photographers, "save_upload_file", fail_save_upload_file)
    monkeypatch.setattr(photographers, "generate_video_thumbnail", fake_generate_thumbnail)
    monkeypatch.setattr(photographers, "save_local_file_to_storage", fake_save_local_file_to_storage)
    monkeypatch.setattr(photographers, "get_video_duration_seconds", lambda _path: 2.5)
    monkeypatch.setattr(photographers, "compress_video", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(photographers, "refresh_ai_resource_documents_for_user", lambda *_args, **_kwargs: None)

    response = client.post(
        "/api/v1/photographers/video/upload",
        headers=photographer_headers,
        data={"title": "Video Work", "compress": "false"},
        files={"file": ("clip.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 200, response.text
    work = response.json()["work"]
    assert work["thumbnail_url"] == "/static/videos/covers/generated-thumb.jpg"
    assert calls["generated"][0] == str(video_path)
    assert Path(calls["generated"][1]).parts[-2:] == ("videos", "covers")
    assert calls["generated"][2] == 30
    assert calls["stored"] == (
        str(thumb_path),
        "videos/covers",
        "clip_thumb.jpg",
        "image/jpeg",
    )
