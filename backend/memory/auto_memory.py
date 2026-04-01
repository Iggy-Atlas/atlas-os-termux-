from .cloud_memory import save_memory

def auto_save(user_msg: str, response: str):
    try:
        data = {
            "user": user_msg[:300],
            "assistant": response[:500]
        }
        save_memory(data)
    except:
        pass
