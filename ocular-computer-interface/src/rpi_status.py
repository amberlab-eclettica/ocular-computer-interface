import subprocess

def get_throttled():
    """
    Returns the throttled status as an integer.
    """
    try:
        out = subprocess.check_output(["vcgencmd", "get_throttled"]).decode()
        # Format: throttled=0x50005
        if "=" in out:
            value = out.strip().split("=")[1]
            return int(value, 16)
    except Exception as e:
        print("Error reading throttled:", e)
    return 0

def is_undervoltage(throttled=None):
    throttled = throttled or get_throttled()
    return bool(throttled & 0x1)

def is_arm_freq_limited(throttled=None):
    throttled = throttled or get_throttled()
    return bool(throttled & 0x4)

def is_throttled_now(throttled=None):
    throttled = throttled or get_throttled()
    return bool(throttled & 0x2)

def get_voltage(core="core"):
    """
    Returns the voltage in volts for a given domain: core, sdram_c, sdram_i, sdram_p
    """
    try:
        out = subprocess.check_output(["vcgencmd", "measure_volts", core]).decode()
        # Format: volt=1.2000V
        value = out.strip().split("=")[1].replace("V","")
        return float(value)
    except Exception as e:
        print("Error reading voltage:", e)
        return None

def get_temp():
    """
    Returns CPU temperature in Celsius.
    """
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        # Format: temp=45.2'C
        value = out.strip().split("=")[1].replace("'C","")
        return float(value)
    except Exception as e:
        print("Error reading temperature:", e)
        return None

def report():
    throttled = get_throttled()
    status = {
        "undervoltage": is_undervoltage(throttled),
        "throttled": is_throttled_now(throttled),
        "arm_limited": is_arm_freq_limited(throttled),
        "voltage_core": get_voltage("core"),
        "temp": get_temp()
    }
    return status

if __name__ == "__main__":
    import time
    while True:
        s = report()
        print(
            f"Undervoltage: {s['undervoltage']}, Throttled: {s['throttled']}, "
            f"ARM freq limited: {s['arm_limited']}, Core voltage: {s['voltage_core']}V, "
            f"Temp: {s['temp']}C"
        )
        time.sleep(2)
