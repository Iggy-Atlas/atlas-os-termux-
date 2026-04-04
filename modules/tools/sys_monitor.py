import os

def get_sys_status():
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[0]
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            total = int(lines[0].split()[1])
            avail = int(lines[2].split()[1])
            usage = round(100 - (avail / total * 100), 1)
        return f"CPU: {load} | RAM: {usage}%"
    except:
        return "Status: Online"
