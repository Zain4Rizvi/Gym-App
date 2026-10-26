import pytest

from api.app.storage import _token_hash, load_accounts, register_account, save_accounts


@pytest.fixture(autouse=True)
def isolated_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "isolated"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def pin():
    register_account("tester@example.com", "secret")
    accounts = load_accounts()
    accounts[-1]["sessions"] = [_token_hash("test-token")]
    save_accounts(accounts)
