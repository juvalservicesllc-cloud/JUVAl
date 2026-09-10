"""Export JUnit counters with explicit tested revision/environment, never logs.

The caller must identify the checkout actually tested; neither origin/master
nor the portal's own checkout establishes the provenance of an external report.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def main():
    portal = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=portal / 'data/generated/backend-junit.xml')
    parser.add_argument('--output', type=Path, default=portal / 'data/generated/test-run.json')
    parser.add_argument('--tested-commit', required=True)
    parser.add_argument('--environment', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-f0-9]{40}', args.tested_commit):
        parser.error('tested-commit must be the full Git commit actually tested')
    suites = list(ET.parse(args.report).getroot().iter('testsuite'))
    if not suites:
        parser.error('JUnit report contains no testsuite')
    total = failed = skipped = 0
    for suite in suites:
        counts = [int(suite.get(key, 0)) for key in ('tests', 'failures', 'errors', 'skipped')]
        tests, failures, errors, skips = counts
        if any(n < 0 for n in counts) or failures + errors + skips > tests:
            parser.error('JUnit counters are inconsistent')
        total += tests
        failed += failures + errors
        skipped += skips
    record = {'total': total, 'passed': total-failed-skipped, 'failed': failed,
              'skipped': skipped, 'at': datetime.now(timezone.utc).isoformat(),
              'head': args.tested_commit, 'environment': args.environment,
              'scope': 'Backend pytest suite; separate from portal tests',
              'provenance': 'Caller-declared tested revision and environment; JUnit counters parsed',
              'failures': [], 'failureDetails': 'NOT_EXPORTED'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2), encoding='utf8')
    print('JUnit counters recorded; no test output or credential values exported.')


if __name__ == '__main__':
    main()
