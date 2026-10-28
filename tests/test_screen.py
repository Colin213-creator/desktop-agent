from desktop_agent.perception.screen import ScreenShot, capture, set_backend, to_absolute


def test_normalized_to_absolute_with_dpi_scale(tmp_path):
    shot = ScreenShot(
        path=tmp_path / "a.png",
        width=1920,
        height=1080,
        scale=1.25,
        active_window="记事本",
        cursor=(10, 10),
    )
    assert to_absolute(500, 500, shot) == (1200, 675)


def test_capture_writes_png(tmp_path):
    set_backend(lambda p: (p.write_bytes(b"\x89PNG"), 800, 600, 1.0, "测试", (0, 0)))
    shot = capture(tmp_path)
    assert shot.path.exists() and shot.width == 800
