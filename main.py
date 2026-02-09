import json
import os
import random

import google.generativeai as genai

from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks

from gestures import (
    GESTURE_MAP,
    init_gestures,
    play_correct_guess,
    play_no_hear,
    play_wrong_guess,
)
from stt import build_microphone, build_recognizer, try_listen_from_mic
from tts import say_text, say_text_with_prompt_gesture, speak_with_gestures

TARGET_WORDS = [
    "football",
    "bicycle",
    "pizza",
    "piano",
    "rainbow",
]
LAST_WORD = None


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
    return response.text.strip().replace("\n", " ")


def wants_more_hint(text):
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return False
    yes_words = {"yes", "yeah", "yep", "sure", "ok", "okay", "more", "hint"}
    return any(word in normalized for word in yes_words)


def wants_no_hint(text):
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return False
    no_words = {"no", "nope", "nah", "stop", "quit", "enough", "exit"}
    return any(word in normalized for word in no_words)


def normalize_text(text):
    if isinstance(text, (list, tuple)):
        if not text:
            return ""
        text = text[-1]
    if text is None:
        return ""
    return str(text)


def parse_role_choice(text):
    normalized = normalize_text(text).lower().strip()
    if "director" in normalized or "direct" in normalized or "leader" in normalized:
        return "director"
    if "matcher" in normalized or "match" in normalized:
        return "matcher"
    if "guesser" in normalized or "guess" in normalized:
        return "matcher"
    return None


def parse_replay_choice(text):
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return None
    if wants_no_hint(normalized):
        return "stop"
    role = parse_role_choice(normalized)
    if role:
        return role
    return None


def listen_text(recognizer, microphone):
    return normalize_text(try_listen_from_mic(recognizer, microphone))


def get_robot_guess(user_description):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = (
        "You are the matcher in a guessing game.\n"
        "Guess the single word that best matches this description:\n"
        f'"{user_description}".\n'
        "Respond in JSON with keys: guess (string), confidence (0 to 1)."
    )
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()
    try:
        data = json.loads(text)
        guess = data.get("guess", "").strip()
        confidence = float(data.get("confidence", 0))
        return guess, confidence
    except (json.JSONDecodeError, ValueError, TypeError):
        return text.splitlines()[0], 0.0


# --- MAIN ---
@inlineCallbacks
def main(session, details):
    print("Robot connected!")

    # 1. Dialogue settings (from the manual)
    yield session.call("rie.dialogue.config.language", lang="en")
    yield init_gestures(session)

    # 2. Game Setup (WOW: choose roles)
    configure_genai()
    recognizer = build_recognizer()
    microphone = build_microphone()

    yield session.call("rom.optional.behavior.play", name="BlocklyWaveRightArm")
    yield say_text(
        session,
        "Hi! My name is Alpha. Let's play WOW.",
    )

    role_choice = None
    while True:
        while role_choice is None:
            yield say_text_with_prompt_gesture(
                session,
                "Do you want to play as a director or a guesser?",
            )
            role_reply = listen_text(recognizer, microphone)
            if wants_no_hint(role_reply):
                yield say_text(session, "Okay, thanks for playing.")
                session.leave()
                return
            role_choice = parse_role_choice(role_reply)
            if role_choice is None:
                yield say_text_with_prompt_gesture(
                    session,
                    "Please say director or guesser.",
                )

        # If human is director, robot is matcher
        if role_choice == "director":
            yield session.call("rom.optional.behavior.play", name="BlocklyStand")
            yield say_text(
                session,
                "Okay, you are the director. I am the matcher.",
            )
            yield say_text_with_prompt_gesture(
                session,
                "Type the target word in the terminal.",
            )
            print("Enter the target word for the robot to guess: ", end="", flush=True)
            target_word = input().strip()
            if not target_word:
                target_word = "football"
            attempts = 0
            hint_requests = 0
            guessed = False
            while not guessed and attempts < 3:
                yield say_text_with_prompt_gesture(session, "Please describe the word.")
                description = listen_text(recognizer, microphone)
                if not description:
                    yield say_text_with_prompt_gesture(
                        session,
                        "I did not hear you. Please try again.",
                    )
                    yield play_no_hear(session)
                    continue
                guess, confidence = get_robot_guess(description)
                if confidence < 0.55 and hint_requests < 3:
                    hint_requests += 1
                    yield say_text_with_prompt_gesture(
                        session,
                        "I am not sure. Can you give another hint?",
                    )
                    continue
                yield say_text(session, f"My guess is {guess}.")
                if target_word.lower() == guess.lower():
                    guessed = True
                    yield say_text(session, "Yes! I guessed it!")
                    yield play_correct_guess(session)
                else:
                    attempts += 1
                    if attempts < 3:
                        yield play_wrong_guess(session)
                        yield say_text_with_prompt_gesture(
                            session,
                            "I will try again. Give me another hint.",
                        )
            if not guessed:
                yield say_text(session, "Good game! I will get it next time.")
        else:
            # Human is matcher, robot is director
            global LAST_WORD
            choices = [word for word in TARGET_WORDS if word != LAST_WORD]
            if not choices:
                choices = TARGET_WORDS[:]
            target_word = random.choice(choices)
            LAST_WORD = target_word
            script = get_robot_description(target_word)

            print(f"Target Word: {target_word}")

            # 3. Robot Actions
            yield session.call("rom.optional.behavior.play", name="BlocklyStand")
            yield say_text(
                session,
                "Let's play WOW. I will describe a word with other words. "
                "Try to guess it.",
            )
            yield speak_with_gestures(session, script, GESTURE_MAP)

            # Optional extra hints
            max_hints = 3
            hints_given = 0
            while hints_given < max_hints:
                yield say_text_with_prompt_gesture(
                    session,
                    "Do you want another hint?",
                )
                reply = listen_text(recognizer, microphone)
                if not reply:
                    yield say_text_with_prompt_gesture(
                        session,
                        "Please say yes or no.",
                    )
                    yield play_no_hear(session)
                    continue
                if wants_no_hint(reply):
                    break
                if not wants_more_hint(reply):
                    yield say_text_with_prompt_gesture(session, "Please say yes or no.")
                    continue
                hints_given += 1
                script = get_robot_description(target_word)
                yield speak_with_gestures(session, script, GESTURE_MAP)

            yield say_text_with_prompt_gesture(
                session,
                "What word am I describing?",
            )

            guessed = False
            attempts = 0
            while not guessed and attempts < 3:
                guess = listen_text(recognizer, microphone)
                if not guess:
                    yield say_text_with_prompt_gesture(
                        session,
                        "I did not hear you. Please say it again.",
                    )
                    yield play_no_hear(session)
                    continue
                if target_word.lower() in guess.lower():
                    guessed = True
                    yield say_text(session, "Correct! Woohoo!")
                    yield play_correct_guess(session)
                else:
                    attempts += 1
                    if attempts < 3:
                        yield play_wrong_guess(session)
                        yield say_text(session, "Nope, try again.")

            if not guessed:
                yield say_text(
                    session,
                    f"Good try. The word was {target_word}.",
                )

        replay_choice = None
        while replay_choice is None:
            yield say_text_with_prompt_gesture(
                session,
                "Play again as director, matcher, or stop?",
            )
            replay_reply = listen_text(recognizer, microphone)
            replay_choice = parse_replay_choice(replay_reply)
            if replay_choice is None:
                yield say_text_with_prompt_gesture(
                    session,
                    "Please say director, matcher, or stop.",
                )
                yield play_no_hear(session)
        if replay_choice == "stop":
            yield say_text(session, "Thanks for playing!")
            break
        role_choice = replay_choice

    session.leave()


wamp = Component(
    transports=[
        {
            "url": "ws://wamp.robotsindeklas.nl",
            "serializers": ["msgpack"],
            "max_retries": 0,
        }
    ],
    realm="rie.6989affd946951d690d126f9",
)
wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])