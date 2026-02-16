from alpha_mini_rug.speech_to_text import SpeechToText
from autobahn.twisted.util import sleep
from twisted.internet.defer import inlineCallbacks

HEARING_SENSITIVITY = 1400
SILENCE_TIME = 2.5  # Increased to allow longer pauses between words
SILENCE_THRESHOLD = 600


class RobotSTT:
    def __init__(self):
        self.audio = SpeechToText()
        # Manual suggests tuning this value (100-500 typical).
        # We use a higher threshold to ignore ambient fan/noise.
        self.audio.silence_time = SILENCE_TIME
        self.audio.silence_threshold2 = SILENCE_THRESHOLD
        self.audio.logging = False
        self.audio.do_speech_recognition = True
        print(
            "[STT] Robot microphone initialized "
            f"(silence_time={SILENCE_TIME}, threshold={SILENCE_THRESHOLD})"
        )


@inlineCallbacks
def start_robot_mic(session, robot_stt):
    yield session.call("rom.sensor.hearing.sensitivity", HEARING_SENSITIVITY)
    yield session.call("rie.dialogue.config.language", lang="en")
    # Only one subscriber as recommended in the manual
    yield session.subscribe(robot_stt.audio.listen_continues, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")
    print(f"[STT] Hearing stream started (sensitivity={HEARING_SENSITIVITY})")


@inlineCallbacks
def stop_robot_mic(session):
    yield session.call("rom.sensor.hearing.close")


# Minimum length for "heard in phrase" to count as echo (so we don't ignore "yes"/"no")
_MIN_ECHO_LENGTH = 12


def _is_robot_self_heard(heard_text, ignore_phrases):
    """True if heard_text is likely the robot's own TTS (matches something we should ignore)."""
    if not ignore_phrases or not heard_text:
        return False
    h = str(heard_text).lower().strip()
    for phrase in ignore_phrases:
        p = str(phrase).lower().strip()
        if not p:
            continue
        if h == p:
            return True
        # Robot's phrase is contained in what we heard (user/echo repeated the prompt)
        if p in h and len(h) - len(p) < 20:
            return True
        # Heard text is contained in robot's phrase - only treat as echo if heard is long enough,
        # so we don't ignore short valid answers like "yes" or "no" that happen to appear in the prompt
        if h in p and len(p) - len(h) < 20 and len(h) >= _MIN_ECHO_LENGTH:
            return True
    return False


@inlineCallbacks
def listen_from_robot(session, robot_stt, timeout_seconds=12, ignore_phrases=None):
    # Clear buffer to prevent hearing robot's own voice
    robot_stt.audio.words = []
    robot_stt.audio.new_words = False

    # Grace period: ignore any speech for 2s after we start (catches TTS echo)
    yield sleep(2.0)
    robot_stt.audio.words = []
    robot_stt.audio.new_words = False

    waited = 0.0
    while True:
        if not robot_stt.audio.new_words:
            robot_stt.audio.loop()
            yield sleep(0.5)
            waited += 0.5
            if waited >= timeout_seconds:
                print("[STT] Robot mic heard: (timeout)")
                return ""
            continue
        words = robot_stt.audio.give_me_words()
        if words:
            text = words[-1]
            if isinstance(text, (list, tuple)):
                text = text[0] if text else ""
            text = str(text).strip() if text else ""
            if _is_robot_self_heard(text, ignore_phrases):
                print(f"[STT] Ignoring (robot's own voice): {text!r}")
                robot_stt.audio.words = []
                robot_stt.audio.new_words = False
                continue
            print(f"[STT] Robot mic heard: {text}")
            return text
