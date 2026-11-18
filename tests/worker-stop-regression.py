"""Exercise the release's real stop function without importing application state."""
import ast
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest

source = Path(__file__).resolve().parents[1] / 'backend/bot_manager.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_terminate_process')
scope = {'os': os, 'signal': signal, 'subprocess': subprocess}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
terminate = scope['_terminate_process']

class StopRegression(unittest.TestCase):
    def test_real_subprocess_with_none_signal_return_is_confirmed_stopped(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            self.assertEqual(terminate(process), (True, 'stopped'))
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_explicit_signal_failure_stays_unconfirmed(self):
        class RejectedSignal:
            def poll(self):
                return None
            def send_signal(self, value):
                return False
        self.assertEqual(terminate(RejectedSignal()), (False, 'stop_failed'))

    def test_real_subprocess_that_ignores_term_is_killed(self):
        process = subprocess.Popen(
            [sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); time.sleep(60)'],
            start_new_session=True, stdout=subprocess.PIPE, text=True,
        )
        class BoundedWait:
            poll = process.poll
            send_signal = process.send_signal
            def wait(self, timeout):
                return process.wait(timeout=min(timeout, 0.3))
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            self.assertEqual(terminate(BoundedWait()), (True, 'stopped'))
            self.assertEqual(process.returncode, -signal.SIGKILL)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdout.close()

    def test_exited_process_is_already_dead(self):
        process = subprocess.Popen([sys.executable, '-c', 'pass'])
        process.wait(timeout=5)
        self.assertEqual(terminate(process), (True, 'already_dead'))

if __name__ == '__main__':
    unittest.main()
