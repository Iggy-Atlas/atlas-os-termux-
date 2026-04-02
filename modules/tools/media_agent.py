# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - IMAGO
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# This software is the intellectual property of Iggy-Atlas.
# ---------------------------------------------------------

import os
import subprocess
from PIL import Image, ImageEnhance

def process_image(input_path, action="optimize"):
    """Osnovna obrada slika koristeći Pillow."""
    try:
        with Image.open(input_path) as img:
            output_path = input_path.replace(".", "_proc.")
            
            if action == "optimize":
                # Smanjuje veličinu bez vidljivog gubitka kvalitete
                img.save(output_path, "JPEG", quality=85, optimize=True)
            elif action == "grayscale":
                img.convert("L").save(output_path)
            elif action == "enhance":
                # Pojačava kontrast i oštrinu
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
                img.save(output_path)
                
            return f"✅ Slika obrađena: {output_path}"
    except Exception as e:
        return f"❌ Greška u obradi slike: {e}"

def extract_audio(video_path):
    """Izvlači MP3 iz videa koristeći FFmpeg."""
    output_audio = video_path.rsplit(".", 1)[0] + ".mp3"
    try:
        cmd = f"ffmpeg -i {video_path} -q:a 0 -map a {output_audio} -y"
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"✅ Audio izvučen: {output_audio}"
    except Exception as e:
        return f"❌ FFmpeg greška: {e}"
