from desktop_agent.perception.uitree import (
    UIElement,
    click_element,
    find_elements,
    set_backend,
)


def test_find_returns_matching_control():
    set_backend(
        lambda hint, title, limit: [
            UIElement("保存", "Button", (10, 20, 60, 30), "btnSave"),
            UIElement("取消", "Button", (80, 20, 60, 30), "btnCancel"),
        ]
    )
    got = find_elements("保存")
    assert len(got) == 1
    assert got[0].automation_id == "btnSave"


def test_click_element_returns_false_when_offscreen():
    offscreen = UIElement("X", "Button", (-9999, -9999, 10, 10), "x")
    assert click_element(offscreen) is False
