"""Ajustes del arnes de navegador: las vistas usan dos atributos de fila."""
from pathlib import Path
p = Path('maintenance/browser_smoke.py')
s = p.read_text(encoding='utf-8')
s = s.replace("page.locator('[data-learning-id]').first.click()", "page.locator('[data-learning-row], [data-learning-id]').first.click()")
s = s.replace("page.locator('#aiNeuralSvg').wait_for(timeout=20000)", "page.locator('#aiNeuralSvg').wait_for(timeout=20000)\n                        page.screenshot(path=str(output/(name+'-ia-inicial.png')),full_page=True)")
p.write_text(s, encoding='utf-8')
