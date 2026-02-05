import speech_recognition as sr


def listen_from_mic(recognizer, microphone):
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
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
    return sr.Recognizer()


def build_microphone():
    return sr.Microphone()
