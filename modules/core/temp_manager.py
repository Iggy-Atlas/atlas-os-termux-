import os
import uuid

BASE_PATH = os.path.join(os.path.expanduser("~"), "atlas_os_v1", "tmp")

os.makedirs(BASE_PATH, exist_ok=True)

def create_temp_file(code: str, ext: str = "py") -> str:
    filename = f"tmp_{uuid.uuid4().hex[:8]}.{ext}"
    full_path = os.path.join(BASE_PATH, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(code)

    return full_path

def cleanup_temp_files(limit=20):
    files = sorted(
        [os.path.join(BASE_PATH, f) for f in os.listdir(BASE_PATH)],
        key=os.path.getmtime
    )

    if len(files) > limit:
        for f in files[:-limit]:
            try:
                os.remove(f)
            except:
                pass
