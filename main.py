import json
import os
import random

import google.generativeai as genai

from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks

from stt import build_microphone, build_recognizer, try_listen_from_mic
from tts import say_text, speak_with_gestures

GESTURE_MAP = {
    "WAVE": "BlocklyWaveRightArm",
    "STAND": "BlocklyStand",
    "NOD": "BlocklyNod",
    "LOOK_DOWN": "BlocklyLookDown"
}

TARGET_WORDS = [
    "football",
    "bicycle",
    "pizza",
    "piano",
    "rainbow",
]


def load_api_key():
    env_key = os.getenv("GOOGLE_API_KEY")
    if env_key:
        return env_key

    secrets_path = os.path.join(os.path.dirname(__file__), "secrets.json")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                return data.get("GOOGLE_API_KEY")
        except (OSError, json.JSONDecodeError):
            return None
    return None


def configure_genai():
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError(
            "Missing GOOGLE_API_KEY. Set it as an environment variable or "
            "add it to secrets.json."
        )
    genai.configure(api_key=api_key)


def get_robot_description(target_word):
    model = genai.GenerativeModel("gemini-2.5-flash")
    available_actions = ", ".join([f"[{k}]" for k in GESTURE_MAP.keys()])
    prompt = (
        "You are a social robot playing a guessing game.\n"
        f'Target word: "{target_word}".\n'
        "1. Describe it without saying the word.\n"
        f"2. Use gesture tags like {available_actions}.\n"
        "3. Keep it very short.\n"
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# --- MAIN ---
@inlineCallbacks
def main(session, details):
    print("Robot connected!")

    # 1. Dialogue settings (from the manual)
    yield session.call("rie.dialogue.config.language", lang="en")

    # 2. Game Setup (WOW: guess the word with other words)
    configure_genai()
    target_word = random.choice(TARGET_WORDS)
    script = get_robot_description(target_word)

    print(f"Target Word: {target_word}")

    # 3. Robot Actions
    yield session.call("rom.optional.behavior.play", name="BlocklyStand")
    yield say_text(
        session,
        "Let's play WOW. I will describe a word with other words. Try to guess it.",
    )
    yield speak_with_gestures(session, script, GESTURE_MAP)

    # 4. Guessing (laptop microphone)
    recognizer = build_recognizer()
    microphone = build_microphone()
    yield say_text(session, "What word am I describing?")

    guessed = False
    attempts = 0
    while not guessed and attempts < 3:
        guess = try_listen_from_mic(recognizer, microphone)
        if target_word.lower() in guess.lower():
            guessed = True
            yield say_text(session, "Correct!")
            yield session.call("rom.optional.behavior.play", name="BlocklyNod")
        else:
            attempts += 1
            if attempts < 3:
                yield say_text(session, "Nope, try again.")

    if not guessed:
        yield say_text(session, f"Good try. The word was {target_word}.")

    session.leave()


wamp = Component(
    transports=[
        {
            "url": "ws://wamp.robotsindeklas.nl",
            "serializers": ["msgpack"],
            "max_retries": 0,
        }
    ],
    realm="rie.69846c5e8e17491bb13c9ab2",
)
wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])