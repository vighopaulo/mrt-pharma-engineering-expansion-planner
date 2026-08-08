from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
required = [
    'app.py',
    'requirements.txt',
    'models.py',
    'optimization.py',
    'engineering.py',
    'finance.py',
    'reporting_engine.py',
    'radionuclides.json',
]
missing = [item for item in required if not (ROOT/item).exists()]
if missing:
    print('Missing deployment files:')
    for item in missing: print(' -', item)
    sys.exit(1)
text = (ROOT/'app.py').read_text(encoding='utf-8')
if 'from ui.streamlit_app import *' in text:
    print('Unsafe wrapper import remains in app.py.')
    sys.exit(1)
print('Deployment structure verified.')
