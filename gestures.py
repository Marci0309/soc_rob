import random

from twisted.internet.defer import inlineCallbacks

GESTURE_MAP = {
    "WAVE": "BlocklyWaveRightArm",
    "STAND": "BlocklyStand",
    "NOD": "BlocklyBow",
    "LOOK_DOWN": "BlocklyLookAtChild",
}

IDLE_GESTURES = [
    "BlocklyLookAtChild",
    "BlocklyLookingUp",
    "BlocklyShrug",
    "BlocklyWaveRightArm",
]

HEAD_SCRATCH = "BlocklyTouchHead"
SHAKE_HEAD = "BlocklyShrug"
CELEBRATE = "BlocklyApplause"

_available_behaviors = None

_fallback_keywords = {
    "HEAD_SCRATCH": ["touch", "head"],
    "SHAKE_HEAD": ["shrug"],
    "CELEBRATE": ["applause", "clap", "cheer", "dance"],
    "WAVE": ["wave"],
    "NOD": ["bow"],
    "LOOK_DOWN": ["look", "child", "down"],
    "STAND": ["stand", "standup", "stand_up"],
}


@inlineCallbacks
def init_gestures(session):
    global _available_behaviors
    try:
        info = yield session.call("rom.optional.behavior.info")
        behaviors = info.get("behaviors") or info.get("list") or []
        _available_behaviors = {
            name for name in behaviors if isinstance(name, str)
        }
    except Exception:
        _available_behaviors = set()


def _resolve_by_keywords(keywords):
    if not _available_behaviors:
        return None
    for name in _available_behaviors:
        lower = name.lower()
        if all(key in lower for key in keywords):
            return name
    for name in _available_behaviors:
        lower = name.lower()
        if any(key in lower for key in keywords):
            return name
    return None


def resolve_behavior(name, fallback_key=None):
    if _available_behaviors is None:
        return name
    if name in _available_behaviors:
        return name
    if fallback_key and fallback_key in _fallback_keywords:
        replacement = _resolve_by_keywords(_fallback_keywords[fallback_key])
        if replacement:
            return replacement
    return name


@inlineCallbacks
def play_behavior(session, name, fallback_key=None):
    if _available_behaviors is None:
        yield init_gestures(session)
    resolved = resolve_behavior(name, fallback_key=fallback_key)
    try:
        print(f"[GESTURE] {resolved}")
        yield session.call("rom.optional.behavior.play", name=resolved)
    except Exception as exc:
        print(f"[GESTURE] Failed to play {resolved}: {exc}")


@inlineCallbacks
def play_idle(session):
    yield play_behavior(
        session,
        random.choice(IDLE_GESTURES),
        fallback_key="WAVE",
    )


@inlineCallbacks
def play_no_hear(session):
    yield play_behavior(session, HEAD_SCRATCH, fallback_key="HEAD_SCRATCH")


@inlineCallbacks
def play_wrong_guess(session):
    yield play_behavior(session, SHAKE_HEAD, fallback_key="SHAKE_HEAD")


@inlineCallbacks
def play_correct_guess(session):
    yield play_behavior(session, CELEBRATE, fallback_key="CELEBRATE")
