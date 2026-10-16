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

    def test_verified_rr_and_sec_parallel_are_both_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'GZL'/'SE33'
            folder.mkdir(parents=True)
            variants=[
                ('normal.json',{'cardcode':'GZL/SE33-12','rarity':'RR',
                                'imageURL':'https://example.org/rr.png'}),
                ('special.json',{'cardcode':'GZL/SE33-12','rarity':'SEC',
                                 'imageURL':'https://example.org/sec.png'})
            ]
            for name,row in variants:
                (folder/name).write_text(json.dumps(row),encoding='utf-8')
            files=sorted(folder.glob('*.json'))
            old_cards,old_audit=scan_source(files)
            self.assertEqual(len(old_cards),1)
            self.assertEqual(old_audit['discardedDuplicateFiles'],1)
            approved={'GZL/SE33-12':{'rarities':['RR','SEC']}}
            cards,audit=scan_source(files,verified_variants=approved)
            self.assertEqual(len(cards),2)
            self.assertEqual({x['rarity'] for x in cards},{'RR','SEC'})
            self.assertEqual(audit['uniqueCollectorCodes'],1)
            self.assertEqual(audit['uniquePrintingsByCode'],2)
            self.assertEqual(audit['duplicateCodeFiles'],1)
            self.assertEqual(audit['discardedDuplicateFiles'],0)
            self.assertEqual(audit['verifiedVariantRows'],1)
            self.assertEqual(audit['verifiedConflictCodeGroups'],1)
            self.assertEqual(audit['unresolvedConflictingCodeGroups'],0)

    def test_verified_code_with_unreviewed_rarity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'GZL'/'SE33'
            folder.mkdir(parents=True)
            (folder/'bad.json').write_text(
                json.dumps({'cardcode':'GZL/SE33-12','rarity':'SSP'}),encoding='utf-8')
            with self.assertRaises(ValueError):
                scan_source(sorted(folder.glob('*.json')),
                    verified_variants={'GZL/SE33-12':{'rarities':['RR','SEC']}})

    def test_empty_input_is_reported_not_silently_accepted(self):
        cards,audit=scan_source([])
        self.assertEqual(cards,[])
        self.assertEqual(audit['sourceFiles'],0)
        self.assertEqual(audit['uniquePrintingsByCode'],0)
        self.assertEqual(audit['conflictingCodeGroups'],0)


if __name__=='__main__':
    unittest.main()
