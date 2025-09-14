from gpiozero import RotaryEncoder, Button

# --- Rotary encoder ---
encoder = RotaryEncoder(23, 24, wrap=False, max_steps=0)  # CLK=23, DT=24
sw_btn = Button(25, pull_up=True)

def get_rotation():
    """
    Returns +1 for CW, -1 for CCW, 0 for no movement since last call.
    """
    movement = encoder.steps
    if movement != 0:
        # reset steps after reading
        encoder.steps = 0
        return movement
    return 0

def is_pressed():
    return sw_btn.is_pressed
