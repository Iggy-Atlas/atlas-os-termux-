import re
from datetime import datetime

SUSPICIOUS_PATTERNS = [
    r'import os',
    r'subprocess',
    r'eval\(',
    r'exec\(',
    r'__',
    r'base64',
    r'socket',
]

def analyze_threat(user_msg: str) -> dict:
    for p in SUSPICIOUS_PATTERNS:
        if re.search(p, user_msg.lower()):
            return {
                "threat": True,
                "reason": f"Detected pattern: {p}",
                "time": str(datetime.now())
            }
    return {"threat": False}

def security_response(threat_data: dict) -> str:
    return f"[SECURITY ALERT] {threat_data['reason']} @ {threat_data['time']}"
