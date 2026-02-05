import re

from autobahn.twisted.util import sleep
from twisted.internet.defer import inlineCallbacks


@inlineCallbacks
def say_text(session, text):
    print(f"[TTS] {text}")
    yield session.call("rie.dialogue.say", text=text)


@inlineCallbacks
def speak_with_gestures(session, script, gesture_map):
    parts = re.split(r'(\[[A-Z_]+\])', script)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            key = part[1:-1]
            if key in gesture_map:
                print(f"[GESTURE] {key}")
                yield session.call(
                    "rom.optional.behavior.play",
                    name=gesture_map[key],
                )
                yield sleep(1)
        else:
            print(f"[TTS] {part}")
            yield session.call("rie.dialogue.say", text=part)
            yield sleep(len(part) * 0.1 + 0.5)
