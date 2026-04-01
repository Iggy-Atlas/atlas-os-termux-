from .cloud_memory import list_memories

def recall():
    try:
        mems = list_memories()
        return "Zadnje memorije:\n" + "\n".join(mems)
    except:
        return "Memory error."
