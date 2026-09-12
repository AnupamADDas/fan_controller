#!/usr/bin/python3
"""Request full fan after 30 seconds at >=75 C; restore auto below 65 C."""
import argparse
import fcntl
import logging
from pathlib import Path
import signal
import threading
import time

HWMON = Path('/sys/class/hwmon')
FAN_ROOT = Path('/sys/devices/platform/asus-nb-wmi/hwmon')
HIGH = 75000
LOW = 65000
POLL_SECONDS = 2
HOT_SECONDS = 30


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


class FanPolicy:
    def __init__(self):
        self.mode = 2
        self.hot_since = None

    def update(self, temperature, now):
        if self.mode == 0:
            if temperature < LOW:
                self.mode = 2
            self.hot_since = None
        elif temperature >= HIGH:
            if self.hot_since is None:
                self.hot_since = now
            if now - self.hot_since >= HOT_SECONDS:
                self.mode = 0
                self.hot_since = None
        else:
            # Every observed dip below 75 C cancels the pending boost.
            self.hot_since = None
        return self.mode


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
            policy = FanPolicy()
            while not stopped.is_set():
                temperature = cpu_temperature()
                target = policy.update(temperature, time.monotonic())
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
        print('Thresholds: maximum after >=75 C for 30 seconds; automatic at <65 C; polling every 2 seconds')
    elif args.restore_auto:
        restore_auto()
    else:
        run()


if __name__ == '__main__':
    main()
