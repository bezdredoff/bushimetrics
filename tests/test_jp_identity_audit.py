"""JP printing deduplication must be auditable, never guess an edition."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_weiss_jp import scan_source


class JapaneseIdentityAuditTests(unittest.TestCase):
    def test_same_code_dedup_and_conflicting_variants_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'title'/'set'
            directory.mkdir(parents=True)
            files=[
                ('01.json',{'cardcode':'DC/W01-001','jpName':'Sample',
                            'rarity':'R','imageURL':'https://example.org/a.png'}),
                ('02.json',{'cardcode':'DC/W01-001','jpName':'Sample',
                            'rarity':'R','imageURL':'https://example.org/a.png'}),
                ('03.json',{'cardcode':'DC/W01-001','jpName':'Sample',
                            'rarity':'SR','imageURL':'https://example.org/b.png'}),
                ('04.json',{'jpName':'No collector number'}),
                ('05.json',None),
                ('06.json',{'cardcode':'DC/W01-002','jpName':'Another',
                            'rarity':'RR','imageURL':'https://example.org/c.png'})
            ]
            for name,raw in files:
                (directory/name).write_text(
                    '{malformed' if raw is None else json.dumps(raw),encoding='utf-8')
            cards,audit=scan_source(sorted(directory.glob('*.json')))
            self.assertEqual(len(cards),2)
            self.assertEqual(audit['sourceFiles'],6)
            self.assertEqual(audit['parsedFiles'],5)
            self.assertEqual(audit['invalidFiles'],1)
            self.assertEqual(audit['missingCardCodeFiles'],1)
            self.assertEqual(audit['duplicateCodeFiles'],2)
            self.assertEqual(audit['duplicateCodeGroups'],1)
            self.assertEqual(audit['conflictingCodeGroups'],1)
            self.assertEqual(len(audit['conflictExamples']),1)
            self.assertIn('rarity',audit['conflictExamples'][0]['differingFields'])
            self.assertIn('image',audit['conflictExamples'][0]['differingFields'])
            first=next(c for c in cards if c['code']=='DC/W01-001')
            # Keep legacy behavior until a physical variant is independently verified.
            self.assertEqual(first['rarity'],'R')

    def test_empty_input_is_reported_not_silently_accepted(self):
        cards,audit=scan_source([])
        self.assertEqual(cards,[])
        self.assertEqual(audit['sourceFiles'],0)
        self.assertEqual(audit['uniquePrintingsByCode'],0)
        self.assertEqual(audit['conflictingCodeGroups'],0)


if __name__=='__main__':
    unittest.main()
