"""Every Academy chapter (lesson, live widgets, exercises, quiz) renders without error."""

import pytest
from test_app import _open, offline  # noqa: F401  (autouse fixture: offline data double)

from quantforge.academy import load_curriculum


@pytest.mark.parametrize("cid", [c.id for c in load_curriculum()])
def test_chapter_renders(cid, monkeypatch):
    monkeypatch.delenv("QUANTFORGE_ALLOW_CODE_EXECUTION", raising=False)  # public-site mode
    at = _open("16_Academy.py", 300)
    at.selectbox[0].set_value(cid).run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
