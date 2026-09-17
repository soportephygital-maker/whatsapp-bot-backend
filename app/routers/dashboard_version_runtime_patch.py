from . import dashboard_email_milestone_patch as target

UI_VERSION = '2026.09.17-110'
_original_html = target._html


def _html():
    html = _original_html()
    for old in ('2026.09.04-105', '2026.09.04-106', '2026.09.04-107', '2026.09.04-108', '2026.09.17-109'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


target.UI_VERSION = UI_VERSION
target._html = _html
