from . import case_management_patch


def _is_legacy_attachment_post(route) -> bool:
    path = getattr(route, 'path', '')
    methods = set(getattr(route, 'methods', set()) or set())
    return path == '/api/tickets/{ticket_id}/adjuntos' and 'POST' in methods


# The generic case-management uploader was registered before the Android-aware
# uploader, so FastAPI matched it first. Remove only that conflicting POST route.
# GET/list/download routes remain in case_management_patch; the specialized
# case_media_upload_patch POST route now owns Android image uploads and links them
# to the latest image message in the ticket.
case_management_patch.router.routes[:] = [
    route for route in case_management_patch.router.routes
    if not _is_legacy_attachment_post(route)
]
