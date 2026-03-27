import traceback
import io
import sys

class AutoHealer:
    def __init__(self, model_engine):
        self.model_engine = model_engine
        self.max_retries = 3

    async def execute_and_fix(self, code, context=""):
        attempt = 0
        current_code = code
        while attempt < self.max_retries:
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                sys.stdout = stdout
                sys.stderr = stderr
                exec_globals = {"__builtins__": __builtins__}
                exec(current_code, exec_globals)
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                return {"status": "success", "output": stdout.getvalue(), "code": current_code}
            except Exception:
                attempt += 1
                error_msg = traceback.format_exc()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                if attempt < self.max_retries:
                    # Tražimo popravak od AI modela
                    repair_prompt = f"KOD IMA GREŠKU:\n{error_msg}\n\nPOPRAVI OVAJ KOD:\n{current_code}\n\nVrati SAMO čisti Python kod bez kvačica."
                    current_code = await self.model_engine.generate(repair_prompt)
                else:
                    return {"status": "failed", "error": error_msg, "code": current_code}
