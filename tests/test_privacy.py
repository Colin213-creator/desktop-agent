from PIL import Image

from desktop_agent.safety.privacy import Mask, PrivacyPolicy, redact, route_model


def test_redact_blackens_configured_region(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGB", (100, 100), "white").save(src)

    out = redact(src, [Mask((10, 10, 20, 20))], tmp_path / "out.png")

    img = Image.open(out).convert("RGB")
    assert img.getpixel((15, 15)) == (0, 0, 0)
    assert img.getpixel((80, 80)) == (255, 255, 255)


def test_sensitive_policy_routes_to_local_model():
    assert route_model(PrivacyPolicy(cloud_upload=False), "登录网银") == "local"
    assert route_model(PrivacyPolicy(cloud_upload=True), "打开计算器") == "cloud"
