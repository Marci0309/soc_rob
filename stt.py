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


@inlineCallbacks
def listen_from_robot(session, robot_stt, timeout_seconds=12):
    # Clear buffer to prevent hearing robot's own voice
    robot_stt.audio.words = []
    robot_stt.audio.new_words = False
    
    # Small delay to let robot finish speaking completely
    yield sleep(0.5)
    
    # Clear again after delay
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
            print(f"[STT] Robot mic heard: {text}")
            return text
