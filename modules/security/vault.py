import os

def check_access(path):
    path = os.path.abspath(os.path.expanduser(path))
    safe_zone = os.path.expanduser("~/atlas_os_v1")
    if path.startswith(safe_zone):
        return "AUTHORIZED"
    return "PENDING_PERMISSION"
