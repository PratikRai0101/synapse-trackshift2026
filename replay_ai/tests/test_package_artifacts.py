import json

from scripts.package_artifacts import build_manifest


def test_manifest_contains_hashes_and_revision(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "model.py").write_text("model = 1\n")
    manifest = build_manifest(tmp_path)
    assert manifest["schema"] == "intelligence-artifact-bundle.v1"
    assert manifest["files"][0]["path"] == "src/model.py"
    assert len(manifest["files"][0]["sha256"]) == 64


def test_manifest_records_benchmark_hash(tmp_path):
    (tmp_path / "scripts").mkdir()
    benchmark = tmp_path / "scripts" / "benchmark.json"
    benchmark.write_text(json.dumps({"schema": "paired-benchmark.v1"}))
    manifest = build_manifest(tmp_path, benchmark)
    assert manifest["benchmark"]["path"] == "scripts/benchmark.json"
    assert len(manifest["benchmark"]["sha256"]) == 64
