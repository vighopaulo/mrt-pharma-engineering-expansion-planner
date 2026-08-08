from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_required_planner_files_exist():
    required = [
        "app.py",
        "models.py",
        "optimization.py",
        "engineering.py",
        "finance.py",
        "diagnostics.py",
        "reporting_engine.py",
        "requirements.txt",
        "radionuclides.json",
    ]
    missing = [name for name in required if not (ROOT / name).exists()]
    assert not missing, f"Missing required files: {missing}"


def test_optimization_module_retained_and_includes_mrt_function():
    text = (ROOT / "optimization.py").read_text(encoding="utf-8")
    assert "def mrt(" in text
    assert "def conventional(" in text


def test_primary_streamlit_entry_is_root_app():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "streamlit run app.py" in readme
