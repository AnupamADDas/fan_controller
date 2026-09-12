#!/usr/bin/python3
"""Request full fan at 75 C; restore firmware auto below 65 C."""
import argparse
import fcntl
import logging
from pathlib import Path
import signal
import threading

HWMON = Path('/sys/class/hwmon')
FAN_ROOT = Path('/sys/devices/platform/asus-nb-wmi/hwmon')
HIGH = 75000
LOW = 65000
POLL_SECONDS = 2


def fan_path(root=FAN_ROOT):
    paths = list(root.glob('hwmon*/pwm1_enable'))
    if len(paths) != 1:
        raise RuntimeError('Expected exactly one ASUS CPU fan control')
    return paths[0]


def cpu_temperature(root=HWMON):
    values = []
    for device in root.glob('hwmon*'):
        if (device / 'name').read_text().strip() != 'coretemp':
            continue
        for sensor in device.glob('temp*_input'):
            value = int(sensor.read_text().strip())
            if not 0 <= value <= 150000:
                raise RuntimeError('Invalid CPU temperature reading')
            values.append(value)
    if not values:
        raise RuntimeError('No Intel CPU temperature sensors found')
    return max(values)


def desired_mode(current, temperature):
    if temperature >= HIGH:
        return 0
    if temperature < LOW:
        return 2
    return current


def set_mode(mode):
    fan_path().write_text(f'{mode}\n')


def restore_auto():
    set_mode(2)
    logging.info('Restored firmware automatic fan control')


def run():
    stopped = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopped.set())
    # Avoid two controllers racing to write different modes.
    with open('/run/asus-fan-controller.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            restore_auto()
            mode = 2
            while not stopped.is_set():
                temperature = cpu_temperature()
                target = desired_mode(mode, temperature)
                # Also reapply the desired mode if another program changed it.
                actual = int(fan_path().read_text().strip())
                if target != mode or actual != target:
                    set_mode(target)
                    logging.info('CPU %.1f C: %s', temperature / 1000,
                                 'maximum fan requested' if target == 0 else 'firmware automatic')
                mode = target
                stopped.wait(POLL_SECONDS)
        finally:
            # Sensor errors or termination must hand control back to firmware.
            restore_auto()


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read sensors without changing the fan')
    parser.add_argument('--restore-auto', action='store_true', help='Restore firmware automatic control')
    args = parser.parse_args()
    if args.check:
        print(f'CPU: {cpu_temperature() / 1000:.1f} C')
        path = fan_path()
        print(f'Fan control: {path}; mode: {path.read_text().strip()}')
        print('Thresholds: maximum at >=75 C; automatic at <65 C; polling every 2 seconds')
    elif args.restore_auto:
        restore_auto()
    else:
        run()


if __name__ == '__main__':
    main()
