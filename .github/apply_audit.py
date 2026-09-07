"""Aplica la revision auditada solo en el espacio de trabajo de pruebas."""
import base64
import hashlib
import lzma
from pathlib import Path
import runpy
import subprocess
import tempfile

folder = Path('maintenance/revision_79')
encoded = ''.join((folder / f'parte{i}.b64').read_text(encoding='ascii').strip() for i in (1, 2, 3))
patch = lzma.decompress(base64.b64decode(encoded, validate=True))
expected = 'ca53f5d5d91285b04da0d6e87e141220a603334286fd649853ff1e4a39775345'
if hashlib.sha256(patch).hexdigest() != expected:
    raise RuntimeError('No coincide la integridad de la revision')
with tempfile.TemporaryDirectory(prefix='phygital-revision-') as tmp:
    target = Path(tmp) / 'revision.patch'
    target.write_bytes(patch)
    subprocess.run(['git', 'apply', '--check', str(target)], check=True)
    subprocess.run(['git', 'apply', str(target)], check=True)
if (folder / 'ajustes.py').exists():
    runpy.run_path(str(folder / 'ajustes.py'))
print('Revision 79 aplicada al entorno de validacion; el despliegue no se modifica.')
