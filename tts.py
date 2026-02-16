import random
import re

from autobahn.twisted.util import sleep
from twisted.internet.defer import inlineCallbacks

from gestures import play_gesture, play_idle


@inlineCallbacks
def say_text(session, text, gesture=None):
    # Clean and validate text before speaking
    text = str(text).strip()
    # Remove problematic characters
    text = text.replace('"', '').replace("'", '').replace('`', '')
    text = ' '.join(text.split())  # Normalize whitespace
    
    # Skip empty or too short text
    if len(text) < 2:
        print(f"[TTS] Skipped invalid text: '{text}'")
        return
    
    print(f"[TTS] {text}")
    
    # Start gesture simultaneously with speech if provided
    if gesture:
        play_gesture(session, gesture)  # Don't yield - start it in parallel
    
    try:
        yield session.call("rie.dialogue.say", text=text)
    except Exception as exc:
        print(f"[TTS] Failed to speak: {exc}")
    # Shorter pause for faster conversation flow
    yield sleep(0.1)


@inlineCallbacks
def say_text_with_prompt_gesture(session, text):
    # Just speak without random gestures
    yield say_text(session, text)


@inlineCallbacks
def speak_with_gestures(session, script, gesture_map):
    normalized = " ".join(script.replace("\n", " ").split())
    parts = re.split(r'(\[[A-Z_]+\])', normalized)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            key = part[1:-1].strip().upper().replace(" ", "_")
            key = re.sub(r"[^A-Z_]", "", key)
            if key in gesture_map:
                yield play_gesture(session, gesture_map[key])
                yield sleep(0.3)
        else:
            clean_part = re.sub(r"\[[^\]]*\]", " ", part)
            clean_part = " ".join(clean_part.split())
            # Remove problematic characters
            clean_part = clean_part.replace('"', '').replace("'", '').replace('`', '')
            clean_part = clean_part.strip()
            
            # Skip empty or too short text
            if len(clean_part) < 2:
                continue
            
            print(f"[TTS] {clean_part}")
            try:
                yield session.call("rie.dialogue.say", text=clean_part)
            except Exception as exc:
                print(f"[TTS] Failed to speak: {exc}")
            
            # Occasionally add subtle idle gestures (20% chance)
            if random.random() < 0.2:
                yield play_idle(session)
            
            # Much shorter pause between sentences
            pause = min(0.5, max(0.1, len(part) * 0.02))
            yield sleep(pause)
