"""Lightweight hand-landmark helpers shared by the UI and the tests.

The module deliberately has no Qt or camera dependency so it can be exercised
in isolation.
"""

import math
from typing import Iterable, Optional

# A pinch is recognised when the thumb tip and index tip are closer than this
# distance, measured in normalised landmark units.
PINCH_DISTANCE = 0.06


def estimate_gesture_state(
    landmarks: Optional[Iterable[tuple[float, float, float]]],
    screen_size: Optional[tuple[int, int]] = None,
    prev_pinch: bool = False,
) -> dict:
    """Translate hand landmarks into a simplified gesture state.

    ``screen_size`` is accepted for callers that want pixel output; the returned
    cursor stays normalised (0..1) so it can be mapped to any display. The second
    argument may also be a plain boolean for backwards compatibility with
    ``estimate_gesture_state(landmarks, prev_pinch)``.
    """
    if isinstance(screen_size, bool):
        prev_pinch, screen_size = screen_size, None

    if not landmarks or len(landmarks) < 21:
        return {
            "hand_detected": False,
            "cursor": None,
            "cursor_px": None,
            "pinch": False,
            "pinch_triggered": False,
        }

    # landmarks are expected as normalized coordinates (x, y, z) in range [0..1]
    index_tip = landmarks[8]
    thumb_tip = landmarks[4]
    dx = thumb_tip[0] - index_tip[0]
    dy = thumb_tip[1] - index_tip[1]
    distance = math.hypot(dx, dy)
    pinch = distance < PINCH_DISTANCE

    cursor = (float(index_tip[0]), float(index_tip[1]))
    cursor_px = None
    if screen_size and len(tuple(screen_size)) == 2:
        width, height = screen_size
        cursor_px = (int(cursor[0] * width), int(cursor[1] * height))

    return {
        "hand_detected": True,
        "cursor": cursor,
        "cursor_px": cursor_px,
        "pinch": pinch,
        "pinch_triggered": bool(pinch and not prev_pinch),
    }
