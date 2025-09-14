from gpiozero import Button

# --- 8-way switch ---
SWITCH_PINS = [5, 6, 13, 19, 4, 17, 27, 22]
switches = [Button(pin, pull_up=True) for pin in SWITCH_PINS]

def get_position():
    """
    Return the position of the 8-way switch (1-8),
    or None if none pressed.
    """
    for i, sw in enumerate(switches):
        if sw.is_pressed:
            return i + 1
    return None

def report_state():
    states = [str(i+1) if not sw.is_pressed else "-" for i, sw in enumerate(switches)]
    print("Switch states:", " ".join(states))
    return 