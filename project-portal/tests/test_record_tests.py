"""Counter export must never invent a tested checkout or expose JUnit content."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/record-tests.py'


class CounterExportTests(unittest.TestCase):
    def run_export(self, xml, *args):
        with tempfile.TemporaryDirectory() as scratch:
            report = Path(scratch) / 'report.xml'
            output = Path(scratch) / 'out.json'
            report.write_text(xml)
            result = subprocess.run([sys.executable, str(SCRIPT), '--report', str(report),
                                     '--output', str(output), *args], capture_output=True, text=True)
            return result, output.read_text() if output.exists() else None

    def test_explicit_provenance_and_counters_without_raw_details(self):
        result, raw = self.run_export(
            '<testsuites><testsuite tests="4" failures="1" errors="0" skipped="1">'
            '<testcase name="never-export"><failure>private-content</failure></testcase>'
            '</testsuite></testsuites>', '--tested-commit', 'a'*40, '--environment', 'synthetic Linux fixture')
        self.assertEqual(result.returncode, 0)
        record = json.loads(raw)
        self.assertEqual((record['passed'], record['failed'], record['skipped']), (2, 1, 1))
        self.assertEqual(record['head'], 'a'*40)
        self.assertEqual(record['environment'], 'synthetic Linux fixture')
        self.assertNotIn('never-export', raw)
        self.assertNotIn('private-content', raw)

    def test_missing_provenance_is_rejected(self):
        result, raw = self.run_export('<testsuite tests="1"/>')
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(raw)

    def test_inconsistent_counts_are_rejected(self):
        result, raw = self.run_export('<testsuite tests="1" failures="2"/>',
                                     '--tested-commit', 'a'*40, '--environment', 'fixture')
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(raw)


if __name__ == '__main__':
    unittest.main()
