"""Integration tests: 匿名 UUID 进度同步 API"""
import pytest

pytestmark = pytest.mark.integration


class TestProgressNew:
    def test_create_new_pseudo(self, client):
        r = client.post("/api/progress/new")
        assert r.status_code == 200
        data = r.json()
        assert "pseudo_id" in data
        assert "export_token" in data
        assert data["export_token"].startswith("COACH-")
        assert data["progress"] == {}

    def test_each_call_returns_unique_id(self, client):
        a = client.post("/api/progress/new").json()
        b = client.post("/api/progress/new").json()
        assert a["pseudo_id"] != b["pseudo_id"]
        assert a["export_token"] != b["export_token"]

    def test_export_token_format(self, client):
        data = client.post("/api/progress/new").json()
        tok = data["export_token"]
        parts = tok.split("-")
        assert parts[0] == "COACH"
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4


class TestProgressGetSave:
    def test_get_existing_returns_progress(self, client):
        created = client.post("/api/progress/new").json()
        pid = created["pseudo_id"]
        r = client.get(f"/api/progress/{pid}")
        assert r.status_code == 200
        assert r.json()["pseudo_id"] == pid

    def test_get_unknown_returns_404(self, client):
        r = client.get("/api/progress/nonexistent_id_xxx")
        assert r.status_code == 404

    def test_save_progress(self, client):
        created = client.post("/api/progress/new").json()
        pid = created["pseudo_id"]
        prog = {"module_99_test": "done", "module_99_test_completed_at": "2026-05-12T19:00:00Z"}
        r = client.post(f"/api/progress/{pid}", json={"progress": prog})
        assert r.status_code == 200
        # 读回来
        r2 = client.get(f"/api/progress/{pid}")
        assert r2.json()["progress"] == prog

    def test_save_invalid_payload_returns_400(self, client):
        created = client.post("/api/progress/new").json()
        pid = created["pseudo_id"]
        r = client.post(f"/api/progress/{pid}", json={"progress": "not a dict"})
        assert r.status_code == 400

    def test_save_unknown_pseudo_returns_404(self, client):
        r = client.post("/api/progress/nonexistent_xyz", json={"progress": {}})
        assert r.status_code == 404

    def test_save_too_large_returns_413(self, client):
        created = client.post("/api/progress/new").json()
        pid = created["pseudo_id"]
        huge = {f"key_{i}": "x" * 100 for i in range(1000)}
        r = client.post(f"/api/progress/{pid}", json={"progress": huge})
        assert r.status_code == 413


class TestProgressImport:
    def test_import_valid_token_returns_progress(self, client):
        created = client.post("/api/progress/new").json()
        token = created["export_token"]
        pid = created["pseudo_id"]
        # 先存点进度
        client.post(f"/api/progress/{pid}", json={"progress": {"m1": "done"}})
        # 导入
        r = client.post("/api/progress/import", json={"token": token})
        assert r.status_code == 200
        data = r.json()
        assert data["pseudo_id"] == pid
        assert data["progress"] == {"m1": "done"}

    def test_import_unknown_token_returns_404(self, client):
        r = client.post("/api/progress/import", json={"token": "COACH-XXXX-XXXX"})
        assert r.status_code == 404

    def test_import_invalid_format_returns_400(self, client):
        r = client.post("/api/progress/import", json={"token": "not-coach-format"})
        assert r.status_code == 400

    def test_import_missing_token_returns_400(self, client):
        r = client.post("/api/progress/import", json={})
        assert r.status_code == 400

    def test_import_token_case_insensitive(self, client):
        """token 应该接受小写（前端会 upper-case 但 API 也容错）。"""
        created = client.post("/api/progress/new").json()
        token_lower = created["export_token"].lower()
        r = client.post("/api/progress/import", json={"token": token_lower})
        assert r.status_code == 200
