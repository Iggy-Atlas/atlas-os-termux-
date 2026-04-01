import re
from modules.core.temp_manager import create_temp_file, cleanup_temp_files
from modules.core.executor_engine import run_python_file

def extract_python(code_text: str) -> str | None:
    match = re.search(r"```python(.*?)```", code_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def auto_execute(ai_output: str) -> str:
    code = extract_python(ai_output)
    if not code:
        return ai_output

    path = create_temp_file(code)
    result = run_python_file(path)

    cleanup_temp_files()

    return f"{ai_output}\n\n{result}"
