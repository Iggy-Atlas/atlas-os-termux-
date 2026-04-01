memory = []

def remember(item: str):
    memory.append(item)
    if len(memory) > 10:
        memory.pop(0)

def recall():
    return "\n".join(memory[-5:])
