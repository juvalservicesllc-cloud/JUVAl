"""Read JUnit counters only; never export test stdout, failures or credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

portal = Path(__file__).resolve().parents[1]
report = ET.parse(portal / 'data/generated/backend-junit.xml').getroot()
suites = list(report.iter('testsuite'))
total = sum(int(s.get('tests', 0)) for s in suites)
failed = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
skipped = sum(int(s.get('skipped', 0)) for s in suites)
head = subprocess.check_output(['git', 'rev-parse', 'origin/master'], cwd=portal, text=True).strip()
record = {'total': total, 'passed': total-failed-skipped, 'failed': failed, 'skipped': skipped,
          'at': datetime.now(timezone.utc).isoformat(), 'head': head,
          'environment': 'Windows; isolated archive of origin/master; no production credentials loaded',
          'scope': 'Backend pytest suite; separate from portal tests',
          'failures': [case.get('classname', '') + '::' + case.get('name', '')
                       for case in report.iter('testcase')
                       if case.find('failure') is not None or case.find('error') is not None]}
(portal / 'data/generated/test-run.json').write_text(json.dumps(record, indent=2), encoding='utf8')
print(json.dumps(record))
