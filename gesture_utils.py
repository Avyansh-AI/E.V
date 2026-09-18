import math
from typing import Iterable, Optional


def estimate_gesture_state(
    landmarks: Optional[Iterable[tuple[float, float, float]]],
    screen_size: Optional[tuple[int, int] | bool] = None,
    prev_pinch: bool = False,
) -> dict:
    """Translate hand landmarks into a simplified gesture state.

    ``landmarks`` are MediaPipe-style normalized ``(x, y, z)`` tuples. The cursor
    is returned in normalized coordinates so it can be mapped onto any screen;
    ``screen_size`` is accepted for backwards compatibility (and to scale the
    cursor when a size is given). Passing the previous pinch flag as the second
    positional argument keeps older call sites working.

    The implementation intentionally keeps the logic lightweight so it can be
    reused in tests and in the UI without depending on Qt.
    """
    if isinstance(screen_size, bool):
        prev_pinch, screen_size = screen_size, None
    if not landmarks or len(landmarks) < 21:
        return {
            "hand_detected": False,
            "cursor": None,
            "pinch": False,
            "pinch_triggered": False,
        }

    # landmarks are expected as normalized coordinates (x,y,z) in range [0..1]
    index_tip = landmarks[8]
    thumb_tip = landmarks[4]
    dx = thumb_tip[0] - index_tip[0]
    dy = thumb_tip[1] - index_tip[1]
    distance = math.hypot(dx, dy)
    pinch = distance < 0.06

    # Normalized cursor (0..1); scaled to pixels when a screen size was given.
    cursor: tuple[float, float] | tuple[int, int] = (float(index_tip[0]), float(index_tip[1]))
    if screen_size:
        try:
            width, height = (int(screen_size[0]), int(screen_size[1]))
            cursor = (int(cursor[0] * width), int(cursor[1] * height))
        except Exception:
            pass

    return {
        "hand_detected": True,
        "cursor": cursor,
        "pinch": pinch,
        "pinch_triggered": bool(pinch and not prev_pinch),
    }
