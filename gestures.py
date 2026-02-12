import random

from twisted.internet.defer import inlineCallbacks

GESTURE_MAP = {
    "WAVE": "WAVE",
    "STAND": "STAND",
    "NOD": "NOD",
    "LOOK_DOWN": "LOOK_DOWN",
}

IDLE_GESTURES = [
    "NOD",
    "LOOK_DOWN",
    "LOOK_UP",
    "LOOK_LEFT",
    "LOOK_RIGHT",
    "TILT_HEAD",
    "THINKING",
]


def _wave_frames():
    return [
        {"time": 0, "data": {"body.arms.right.upper.pitch": 0.0}},
        {"time": 800, "data": {"body.arms.right.upper.pitch": -1.3}},
        {"time": 1600, "data": {"body.arms.right.upper.pitch": -1.0}},
        {"time": 2400, "data": {"body.arms.right.upper.pitch": -1.3}},
        {"time": 3200, "data": {"body.arms.right.upper.pitch": -1.0}},
        {"time": 4000, "data": {"body.arms.right.upper.pitch": 0.0}},
    ]


def _nod_frames():
    return [
        {"time": 0, "data": {"body.head.pitch": 0.0}},
        {"time": 600, "data": {"body.head.pitch": 0.15}},
        {"time": 1200, "data": {"body.head.pitch": 0.0}},
        {"time": 1800, "data": {"body.head.pitch": 0.15}},
        {"time": 2400, "data": {"body.head.pitch": 0.0}},
    ]


def _shake_head_frames():
    return [
        {"time": 0, "data": {"body.head.yaw": 0.0}},
        {"time": 700, "data": {"body.head.yaw": 0.35}},
        {"time": 1400, "data": {"body.head.yaw": -0.35}},
        {"time": 2100, "data": {"body.head.yaw": 0.35}},
        {"time": 2800, "data": {"body.head.yaw": 0.0}},
    ]


def _look_down_frames():
    return [
        {"time": 0, "data": {"body.head.pitch": 0.0}},
        {"time": 800, "data": {"body.head.pitch": 0.15}},
        {"time": 2200, "data": {"body.head.pitch": 0.0}},
    ]


def _look_up_frames():
    return [
        {"time": 0, "data": {"body.head.pitch": 0.0}},
        {"time": 800, "data": {"body.head.pitch": -0.15}},
        {"time": 2200, "data": {"body.head.pitch": 0.0}},
    ]


def _shrug_frames():
    return [
        {"time": 0, "data": {
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
        }},
        {"time": 900, "data": {
            "body.arms.left.upper.pitch": -0.6,
            "body.arms.right.upper.pitch": -0.6,
        }},
        {"time": 2400, "data": {
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
        }},
    ]


def _touch_head_frames():
    return [
        {"time": 0, "data": {
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.right.lower.roll": 0.0,
        }},
        {"time": 1000, "data": {
            "body.arms.right.upper.pitch": -1.2,
            "body.arms.right.lower.roll": -0.6,
        }},
        {"time": 2500, "data": {
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.right.lower.roll": 0.0,
        }},
    ]


def _applause_frames():
    return [
        {"time": 0, "data": {
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
        }},
        {"time": 700, "data": {
            "body.arms.left.upper.pitch": -1.3,
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.left.lower.roll": -0.8,
            "body.arms.right.lower.roll": -0.8,
        }},
        {"time": 1200, "data": {
            "body.arms.left.upper.pitch": -1.3,
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.left.lower.roll": -0.3,
            "body.arms.right.lower.roll": -0.3,
        }},
        {"time": 1700, "data": {
            "body.arms.left.upper.pitch": -1.3,
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.left.lower.roll": -0.8,
            "body.arms.right.lower.roll": -0.8,
        }},
        {"time": 2200, "data": {
            "body.arms.left.upper.pitch": -1.3,
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.left.lower.roll": -0.3,
            "body.arms.right.lower.roll": -0.3,
        }},
        {"time": 2700, "data": {
            "body.arms.left.upper.pitch": -1.3,
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.left.lower.roll": -0.8,
            "body.arms.right.lower.roll": -0.8,
        }},
        {"time": 3500, "data": {
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
        }},
    ]


def _stand_frames():
    # Gradual stand-up with multiple frames for smooth transition
    # Only upper body - legs controlled by robot's balance system
    return [
        {"time": 0, "data": {
            "body.head.pitch": 0.0,
            "body.head.yaw": 0.0,
            "body.head.roll": 0.0,
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.torso.yaw": 0.0,
        }},
        {"time": 800, "data": {
            "body.head.pitch": 0.0,
            "body.head.yaw": 0.0,
            "body.head.roll": 0.0,
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.torso.yaw": 0.0,
        }},
        {"time": 1600, "data": {
            "body.head.pitch": 0.0,
            "body.head.yaw": 0.0,
            "body.head.roll": 0.0,
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.torso.yaw": 0.0,
        }},
        {"time": 2400, "data": {
            "body.head.pitch": 0.0,
            "body.head.yaw": 0.0,
            "body.head.roll": 0.0,
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.torso.yaw": 0.0,
        }},
        {"time": 3200, "data": {
            "body.head.pitch": 0.0,
            "body.head.yaw": 0.0,
            "body.head.roll": 0.0,
            "body.arms.left.upper.pitch": 0.0,
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.left.lower.roll": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.torso.yaw": 0.0,
        }},
    ]


def _thinking_frames():
    # Elaborate head-scratching motion with 7 frames
    return [
        # Start: arm at rest
        {"time": 0, "data": {
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.head.roll": 0.0,
        }},
        # Raise arm halfway
        {"time": 700, "data": {
            "body.arms.right.upper.pitch": -0.6,
            "body.arms.right.lower.roll": -0.3,
            "body.head.roll": 0.0,
        }},
        # Reach toward head and tilt head slightly
        {"time": 1400, "data": {
            "body.arms.right.upper.pitch": -1.2,
            "body.arms.right.lower.roll": -0.7,
            "body.head.roll": 0.12,
        }},
        # Scratch motion 1 (slight adjustment)
        {"time": 2000, "data": {
            "body.arms.right.upper.pitch": -1.3,
            "body.arms.right.lower.roll": -0.6,
            "body.head.roll": 0.12,
        }},
        # Scratch motion 2 (another adjustment)
        {"time": 2600, "data": {
            "body.arms.right.upper.pitch": -1.2,
            "body.arms.right.lower.roll": -0.7,
            "body.head.roll": 0.12,
        }},
        # Start lowering arm
        {"time": 3200, "data": {
            "body.arms.right.upper.pitch": -0.6,
            "body.arms.right.lower.roll": -0.3,
            "body.head.roll": 0.0,
        }},
        # Return to rest position
        {"time": 4000, "data": {
            "body.arms.right.upper.pitch": 0.0,
            "body.arms.right.lower.roll": 0.0,
            "body.head.roll": 0.0,
        }},
    ]


def _look_left_frames():
    return [
        {"time": 0, "data": {"body.head.yaw": 0.0}},
        {"time": 800, "data": {"body.head.yaw": 0.4}},
        {"time": 2000, "data": {"body.head.yaw": 0.0}},
    ]


def _look_right_frames():
    return [
        {"time": 0, "data": {"body.head.yaw": 0.0}},
        {"time": 800, "data": {"body.head.yaw": -0.4}},
        {"time": 2000, "data": {"body.head.yaw": 0.0}},
    ]


def _tilt_head_frames():
    return [
        {"time": 0, "data": {"body.head.roll": 0.0}},
        {"time": 700, "data": {"body.head.roll": 0.2}},
        {"time": 1400, "data": {"body.head.roll": -0.2}},
        {"time": 2100, "data": {"body.head.roll": 0.0}},
    ]


def _raise_hand_frames():
    # Raise one hand as if asking a question
    return [
        {"time": 0, "data": {"body.arms.left.upper.pitch": 0.0}},
        {"time": 1000, "data": {"body.arms.left.upper.pitch": -1.0}},
        {"time": 2500, "data": {"body.arms.left.upper.pitch": 0.0}},
    ]


MOTION_FRAMES = {
    "WAVE": _wave_frames,
    "NOD": _nod_frames,
    "SHAKE_HEAD": _shake_head_frames,
    "LOOK_DOWN": _look_down_frames,
    "LOOK_UP": _look_up_frames,
    "SHRUG": _shrug_frames,
    "TOUCH_HEAD": _touch_head_frames,
    "APPLAUSE": _applause_frames,
    "STAND": _stand_frames,
    "THINKING": _thinking_frames,
    "LOOK_LEFT": _look_left_frames,
    "LOOK_RIGHT": _look_right_frames,
    "TILT_HEAD": _tilt_head_frames,
    "RAISE_HAND": _raise_hand_frames,
}


@inlineCallbacks
def perform_movement(session, frames):
    try:
        yield session.call(
            "rom.actuator.motor.write",
            frames=frames,
            force=True,
        )
    except Exception as exc:
        print(f"[GESTURE] motor.write failed: {exc}")


@inlineCallbacks
def play_gesture(session, key):
    if key not in MOTION_FRAMES:
        print(f"[GESTURE] Unknown gesture: {key}")
        return
    frames = MOTION_FRAMES[key]()
    print(f"[GESTURE] {key} ({len(frames)} frames)")
    yield perform_movement(session, frames)


@inlineCallbacks
def play_idle(session):
    yield play_gesture(session, random.choice(IDLE_GESTURES))


@inlineCallbacks
def play_no_hear(session):
    # Randomly choose between different "didn't hear" gestures
    gesture = random.choice(["TOUCH_HEAD", "RAISE_HAND", "TILT_HEAD"])
    yield play_gesture(session, gesture)


@inlineCallbacks
def play_wrong_guess(session):
    yield play_gesture(session, "SHAKE_HEAD")


@inlineCallbacks
def play_correct_guess(session):
    yield play_gesture(session, "APPLAUSE")


@inlineCallbacks
def play_wave(session):
    yield play_gesture(session, "WAVE")


@inlineCallbacks
def play_stand(session):
    # Use blockly behavior for proper standing
    try:
        yield session.call("rom.optional.behavior.play", name="BlocklyStand")
    except Exception as exc:
        print(f"[GESTURE] Stand behavior failed: {exc}")
        # Fallback to just resetting upper body
        yield play_gesture(session, "STAND")
