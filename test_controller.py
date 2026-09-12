import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('controller', Path(__file__).with_name('asus-fan-controller.py'))
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class ControllerTests(unittest.TestCase):
    def test_hysteresis_and_exact_boundaries(self):
        mode = 2
        temperatures = [74000, 75000, 71000, 65000, 64999, 70000, 80000]
        modes = []
        for temperature in temperatures:
            mode = controller.desired_mode(mode, temperature)
            modes.append(mode)
        self.assertEqual(modes, [2, 0, 0, 0, 2, 2, 0])

    def test_hottest_cpu_sensor_and_invalid_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cpu = root / 'hwmon42'
            cpu.mkdir()
            (cpu / 'name').write_text('coretemp\n')
            (cpu / 'temp1_input').write_text('74000\n')
            (cpu / 'temp2_input').write_text('76000\n')
            self.assertEqual(controller.cpu_temperature(root), 76000)
            (cpu / 'temp2_input').write_text('999999\n')
            with self.assertRaises(RuntimeError):
                controller.cpu_temperature(root)
            (cpu / 'temp2_input').unlink()
            (cpu / 'temp1_input').unlink()
            with self.assertRaises(RuntimeError):
                controller.cpu_temperature(root)

    def test_missing_or_ambiguous_fan_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                controller.fan_path(root)
            for name in ['hwmon8', 'hwmon9']:
                (root / name).mkdir()
                (root / name / 'pwm1_enable').write_text('2\n')
            with self.assertRaises(RuntimeError):
                controller.fan_path(root)

    def test_sensor_failure_restores_auto_after_requesting_max(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w') as lock:
            pwm = Path(directory) / 'pwm1_enable'
            pwm.write_text('2\n')
            stop = Mock()
            stop.is_set.return_value = False
            with patch.object(controller, 'fan_path', return_value=pwm), \
                 patch.object(controller, 'cpu_temperature', side_effect=[76000, RuntimeError('sensor lost')]), \
                 patch.object(controller.threading, 'Event', return_value=stop), \
                 patch.object(controller.signal, 'signal'), \
                 patch('builtins.open', return_value=lock), \
                 patch.object(controller, 'set_mode', wraps=controller.set_mode) as set_mode:
                with self.assertRaisesRegex(RuntimeError, 'sensor lost'):
                    controller.run()
                self.assertEqual([call.args[0] for call in set_mode.call_args_list], [2, 0, 2])
                self.assertEqual(pwm.read_text().strip(), '2')


if __name__ == '__main__':
    unittest.main()
