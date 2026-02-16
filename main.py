import json
import os
import random

import google.generativeai as genai

from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks

from stt import RobotSTT, listen_from_robot, start_robot_mic, stop_robot_mic
from tts import say_text, say_text_with_prompt_gesture, speak_with_gestures

from gestures import (
    GESTURE_MAP,
    play_correct_guess,
    play_no_hear,
    play_stand,
    play_wave,
    play_wrong_guess,
)

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


def get_robot_description(target_word, previous_descriptions=None):
    """Generate a description of target_word. If previous_descriptions is given, give a NEW hint that does not repeat them."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    available_actions = ", ".join([f"[{k}]" for k in GESTURE_MAP.keys()])
    prompt = (
        "You are a social robot playing a guessing game.\n"
        f'Target word: "{target_word}".\n'
    )
    if previous_descriptions:
        prompt += (
            "You already said these hints (do NOT repeat or rephrase them):\n"
            + "\n".join(f"- {d}" for d in previous_descriptions)
            + "\nGive ONE new, different hint. "
        )
    else:
        prompt += "1. Describe it without saying the word.\n"
    prompt += (
        f"2. Use gesture tags like {available_actions}.\n"
        "3. Keep it very short.\n"
    )
    response = model.generate_content(prompt)
    text = response.text.strip()
    text = text.replace("```", "")
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text


def wants_more_hint(text):
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return False
    yes_words = {"yes", "yeah", "yep", "sure", "ok", "okay", "more", "hint", "another"}
    words = set(normalized.split())
    return any(w in yes_words for w in words)


def wants_no_hint(text):
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return False
    no_words = {"no", "nope", "nah", "stop", "quit", "enough", "exit"}
    words = set(normalized.split())
    return any(w in no_words for w in words)


def wants_to_stop(text):
    """True if user said stop/quit/exit (whole words) — exit the game from anywhere."""
    normalized = normalize_text(text).lower().strip()
    if not normalized:
        return False
    stop_words = {"stop", "quit", "exit", "leave", "end"}
    words = set(normalized.split())
    return any(w in stop_words for w in words)


def normalize_text(text):
    if isinstance(text, (list, tuple)):
        if not text:
            return ""
        # Some STT outputs are tuples like: ("guesser", 0.92)
        for item in text:
            if isinstance(item, str) and item.strip():
                return item
        text = text[0]
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


@inlineCallbacks
def goodbye_and_leave(session):
    yield say_text(session, "Okay, thanks for playing.", gesture="WAVE")
    yield stop_robot_mic(session)
    session.leave()


@inlineCallbacks
def listen_text(session, robot_stt, ignore_phrases=None):
    """Listen for user speech. ignore_phrases: list of strings we just said (TTS) to ignore if mic picks them up."""
    text = yield listen_from_robot(session, robot_stt, ignore_phrases=ignore_phrases)
    return normalize_text(text)


def get_robot_guess(descriptions):
    """Guess the word from one or more descriptions. descriptions can be a string or a list of strings (all hints so far)."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    if isinstance(descriptions, str):
        descriptions = [descriptions]
    combined = " | ".join(descriptions) if descriptions else ""
    prompt = (
        "You are the matcher in a guessing game.\n"
        "The director gave these hints (use ALL of them together to guess):\n"
        f'"{combined}".\n'
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
    # 2. Game Setup (WOW: choose roles)
    configure_genai()
    robot_stt = RobotSTT()
    yield start_robot_mic(session, robot_stt)

    # Stand up first to ensure proper posture
    yield play_stand(session)
    # Wave while introducing itself
    yield say_text(
        session,
        "Hi! My name is Alpha. Let's play WOW.",
        gesture="WAVE"
    )

    role_choice = None
    while True:
        while role_choice is None:
            prompt = "Do you want to play as a director or a guesser?"
            yield say_text_with_prompt_gesture(session, prompt)
            role_reply = yield listen_text(
                session, robot_stt,
                ignore_phrases=[prompt, "Please say director or guesser."],
            )
            if wants_to_stop(role_reply) or wants_no_hint(role_reply):
                yield goodbye_and_leave(session)
                return
            role_choice = parse_role_choice(role_reply)
            if role_choice is None:
                yield say_text(
                    session,
                    "Please say director or guesser.",
                    gesture="TILT_HEAD"
                )

        # If human is director, robot is matcher
        if role_choice == "director":
            yield play_stand(session)
            yield say_text(
                session,
                "Okay, you are the director. I am the guesser.",
                gesture="NOD"
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
            director_descriptions = []  # Remember all hints the director said
            while not guessed and attempts < 3:
                prompt = "Please describe the word."
                yield say_text_with_prompt_gesture(session, prompt)
                description = yield listen_text(session, robot_stt, ignore_phrases=[prompt])
                if wants_to_stop(description):
                    yield goodbye_and_leave(session)
                    return
                if not description:
                    yield say_text(
                        session,
                        "I did not hear you. Please try again.",
                        gesture="TOUCH_HEAD"
                    )
                    continue
                director_descriptions.append(description)
                guess, confidence = get_robot_guess(director_descriptions)
                if confidence < 0.55 and hint_requests < 3:
                    hint_requests += 1
                    yield say_text(
                        session,
                        "I am not sure. Can you give another hint?",
                        gesture="SHRUG"
                    )
                    continue
                yield say_text(session, f"My guess is {guess}.")
                if target_word.lower() == guess.lower():
                    guessed = True
                    yield say_text(session, "Yes! I guessed it!", gesture="APPLAUSE")
                else:
                    attempts += 1
                    if attempts < 3:
                        yield say_text(
                            session,
                            "Nope. I will try again. Give me another hint.",
                            gesture="SHAKE_HEAD"
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
            robot_descriptions = []  # Remember what we already said for extra hints
            script = get_robot_description(target_word)
            robot_descriptions.append(script)

            print(f"Target Word: {target_word}")

            # 3. Robot Actions
            yield play_stand(session)
            yield say_text(
                session,
                "Okay, you are the guesser. I will describe a word. Try to guess it.",
                gesture="NOD"
            )
            yield speak_with_gestures(session, script, GESTURE_MAP)

            # Optional extra hints
            max_hints = 3
            hints_given = 0
            while hints_given < max_hints:
                hint_prompt = "Do you want another hint?"
                yield say_text_with_prompt_gesture(session, hint_prompt)
                reply = yield listen_text(
                    session, robot_stt,
                    ignore_phrases=[hint_prompt, "Please say yes or no."],
                )
                if wants_to_stop(reply):
                    yield goodbye_and_leave(session)
                    return
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
                script = get_robot_description(target_word, previous_descriptions=robot_descriptions)
                robot_descriptions.append(script)
                yield speak_with_gestures(session, script, GESTURE_MAP)

            guess_prompt = "What word am I describing?"
            yield say_text_with_prompt_gesture(session, guess_prompt)

            guessed = False
            attempts = 0
            while not guessed and attempts < 3:
                guess = yield listen_text(
                    session, robot_stt,
                    ignore_phrases=[guess_prompt, "Nope, try again.", "I did not hear you. Please say it again."],
                )
                if wants_to_stop(guess):
                    yield goodbye_and_leave(session)
                    return
                if not guess:
                    yield say_text(
                        session,
                        "I did not hear you. Please say it again.",
                        gesture="TOUCH_HEAD"
                    )
                    continue
                if target_word.lower() in guess.lower():
                    guessed = True
                    yield say_text(session, "Correct! Woohoo!", gesture="APPLAUSE")
                else:
                    attempts += 1
                    if attempts < 3:
                        yield say_text(session, "Nope, try again.", gesture="SHAKE_HEAD")

            if not guessed:
                yield say_text(
                    session,
                    f"Good try. The word was {target_word}.",
                )

        replay_choice = None
        while replay_choice is None:
            replay_prompt = "Play again as director, guesser, or stop?"
            yield say_text_with_prompt_gesture(session, replay_prompt)
            replay_reply = yield listen_text(
                session, robot_stt,
                ignore_phrases=[replay_prompt, "Please say director, guesser, or stop."],
            )
            if wants_to_stop(replay_reply):
                yield goodbye_and_leave(session)
                return
            replay_choice = parse_replay_choice(replay_reply)
            if replay_choice is None:
                yield say_text(
                    session,
                    "Please say director, guesser, or stop.",
                    gesture="TILT_HEAD"
                )
        if replay_choice == "stop":
            yield say_text(session, "Thanks for playing!", gesture="WAVE")
            break
        role_choice = replay_choice

    yield stop_robot_mic(session)
    session.leave()


wamp = Component(
    transports=[
        {
            "url": "ws://wamp.robotsindeklas.nl",
            "serializers": ["msgpack"],
            "max_retries": 0,
        }
    ],
    realm="rie.6992eb2fe14c6bd0843c5ff2",
)
wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])