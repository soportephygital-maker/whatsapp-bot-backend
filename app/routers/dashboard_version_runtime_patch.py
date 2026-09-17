from . import dashboard_email_milestone_patch as target

UI_VERSION = '2026.09.17-132'
_original_html = target._html


def _html():
    html = _original_html()
    for old in ('2026.09.04-105', '2026.09.04-106', '2026.09.04-107', '2026.09.04-108', '2026.09.17-109', '2026.09.17-110', '2026.09.17-111', '2026.09.17-112', '2026.09.17-113', '2026.09.17-114', '2026.09.17-115', '2026.09.17-116', '2026.09.17-117', '2026.09.17-118', '2026.09.17-119', '2026.09.17-120', '2026.09.17-121', '2026.09.17-122', '2026.09.17-123', '2026.09.17-124', '2026.09.17-125', '2026.09.17-126', '2026.09.17-127', '2026.09.17-128', '2026.09.17-129', '2026.09.17-130', '2026.09.17-131'):
        html = html.replace(f'UI {old}', f'UI {UI_VERSION}')
        html = html.replace(f'/dashboard.js?v={old}', f'/dashboard.js?v={UI_VERSION}')
    return html


target.UI_VERSION = UI_VERSION
target._html = _html
