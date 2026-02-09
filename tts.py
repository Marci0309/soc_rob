import random
import re

from autobahn.twisted.util import sleep
from twisted.internet.defer import inlineCallbacks

from gestures import play_idle, play_idle_async, resolve_behavior


@inlineCallbacks
def say_text(session, text):
    print(f"[TTS] {text}")
    yield session.call("rie.dialogue.say", text=text)


@inlineCallbacks
def say_text_with_prompt_gesture(session, text):
    yield play_idle_async(session)
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
                print(f"[GESTURE] {key}")
                behavior_name = resolve_behavior(
                    gesture_map[key],
                    fallback_key=key,
                )
                yield session.call(
                    "rom.optional.behavior.play",
                    name=behavior_name,
                )
                yield sleep(1)
        else:
            clean_part = re.sub(r"\[[^\]]*\]", " ", part)
            clean_part = " ".join(clean_part.split())
            if not clean_part:
                continue
            print(f"[TTS] {clean_part}")
            yield session.call("rie.dialogue.say", text=clean_part)
            if random.random() < idle_chance:
                yield play_idle(session)
            # Shorter pause between sentences for smoother flow
            pause = min(1.2, max(0.2, len(part) * 0.04))
            yield sleep(pause)
