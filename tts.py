import random
import re

from autobahn.twisted.util import sleep
from twisted.internet import reactor
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
    # Small pause between spoken lines for smoother pacing
    yield sleep(0.3)


@inlineCallbacks
def say_text_with_prompt_gesture(session, text):
    # Run gesture fully before speaking to avoid interruption.
    yield play_idle(session)
    yield say_text(session, text)


@inlineCallbacks
def speak_with_gestures(session, script, gesture_map, idle_chance=0.4):
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
                yield sleep(0.5)
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
            if random.random() < idle_chance:
                yield play_idle(session)
            # Shorter pause between sentences for smoother flow
            pause = min(1.2, max(0.2, len(part) * 0.04))
            yield sleep(pause)
