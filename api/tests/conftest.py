import pytest


@pytest.fixture(autouse=True)
def isolated_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "isolated"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
