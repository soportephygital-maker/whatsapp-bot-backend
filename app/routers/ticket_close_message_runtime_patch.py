from . import ticketed_local_bridge

_original_render_placeholders = ticketed_local_bridge._render_placeholders


def _render_placeholders(text: str, *, name: str = '', code: str = '') -> str:
    rendered = _original_render_placeholders(text, name=name, code=code)
    low = rendered.lower()
    closing = any(term in low for term in (
        'finaliz',
        'cerrad',
        'problema solucionado',
        'problema resuelto',
        'atencion terminada',
        'atencion finalizada',
        'gracias por comunicarte',
    ))
    if code and closing and code.lower() not in low:
        rendered = rendered.rstrip() + f'\n\n🎫 Número de ticket: {code}'
    return rendered


ticketed_local_bridge._render_placeholders = _render_placeholders
