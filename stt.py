import speech_recognition as sr

LISTEN_TIMEOUT = 8
PHRASE_TIME_LIMIT = 12
PAUSE_THRESHOLD = 1.2


def listen_from_mic(recognizer, microphone):
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(
            source,
            timeout=LISTEN_TIMEOUT,
            phrase_time_limit=PHRASE_TIME_LIMIT,
        )
    return recognizer.recognize_google(audio)


def try_listen_from_mic(recognizer, microphone):
    try:
        text = listen_from_mic(recognizer, microphone)
        print(f"[STT] Mic heard: {text}")
        return text
    except sr.UnknownValueError:
        print("[STT] Mic heard: (unintelligible)")
        return ""
    except (sr.RequestError, sr.WaitTimeoutError):
        print("[STT] Mic heard: (no speech / timeout)")
        return ""


def build_recognizer():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = PAUSE_THRESHOLD
    return recognizer


def build_microphone():
    return sr.Microphone()
