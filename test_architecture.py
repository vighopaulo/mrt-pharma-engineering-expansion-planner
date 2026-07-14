from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_complete_repository_structure():
    required = [
        'app.py','requirements.txt','ENGINEERING_NOTES.md','constitution/CONSTITUTION.md','domain/models.py',
        'entities/hospital.py','entities/cyclotron.py','entities/scanner.py','entities/rooms.py','entities/radionuclide.py',
        'entities/endpoint.py','entities/decision_profile.py','entities/results.py','engines/validation_engine.py',
        'engines/decay_engine.py','engines/capacity_engine.py','engines/production_engine.py','engines/infrastructure_engine.py',
        'engines/resource_optimization_engine.py','engines/financial_engine.py','engines/decision_engine.py',
        'engines/diagnostics_engine.py','engines/reporting_engine.py','data/radionuclides.json',
        'data/country_profiles.json','data/decision_profiles.json','deployment/DEPLOYMENT_CHECKLIST.md'
    ]
    missing = [item for item in required if not (ROOT/item).exists()]
    assert not missing, missing

def test_root_app_is_not_wrapper():
    text = (ROOT/'app.py').read_text(encoding='utf-8')
    assert 'from ui.streamlit_app import *' not in text
    assert 'st.set_page_config' in text
