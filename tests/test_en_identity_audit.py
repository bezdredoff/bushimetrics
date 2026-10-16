"""English Weiss source integrity: no silent import exclusions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_weiss import scan_source_files


class EnglishWeissIdentityTests(unittest.TestCase):
    def test_duplicate_variant_and_bad_input_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'en-a.json').write_text(json.dumps({
                'lang':'en','name':'Set A','id':'A','cards':[
                    {'num':'A/001','name':'First','rarity':'R','img':None},
                    {'num':'A/001','name':'First','rarity':'R','img':'https://example.org/a.png'},
                    {'num':'A/002','name':'Second','rarity':'RR','img':'https://example.org/b.png'},
                    {'name':'Missing code'},
                    'invalid-row',
                ]
            }),encoding='utf-8')
            (directory/'en-b.json').write_text(json.dumps({
                'lang':'en','name':'Set B','id':'B','cards':[
                    {'num':'A/001','name':'First','rarity':'SP','img':'https://example.org/c.png'}
                ]
            }),encoding='utf-8')
            (directory/'jp.json').write_text(json.dumps({
                'lang':'jp','cards':[{'num':'X/001'}]
            }),encoding='utf-8')
            (directory/'invalid.json').write_text('{malformed',encoding='utf-8')
            cards,audit=scan_source_files(sorted(directory.glob('*.json')))
            self.assertEqual(audit['sourceFiles'],4)
            self.assertEqual(audit['englishSetFiles'],2)
            self.assertEqual(audit['nonEnglishSetFiles'],1)
            self.assertEqual(audit['invalidSetFiles'],1)
            self.assertEqual(audit['cardRows'],6)
            self.assertEqual(audit['validCodeRows'],4)
            self.assertEqual(audit['missingCodeRows'],1)
            self.assertEqual(audit['invalidCardRows'],1)
            self.assertEqual(audit['duplicateCodeRows'],2)
            self.assertEqual(audit['duplicateCodeGroups'],1)
            self.assertEqual(audit['conflictingCodeGroups'],1)
            self.assertEqual(len(cards),2)
            a=next(x for x in cards if x['code']=='A/001')
            self.assertEqual(a['rarity'],'R')
            self.assertEqual(a['image'],'https://example.org/a.png')
            self.assertIn('rarity',audit['conflictExamples'][-1]['differingFields'])

    def test_empty_input_reported(self):
        cards,audit=scan_source_files([])
        self.assertEqual(cards,[])
        self.assertEqual(audit['uniquePrintingsByCode'],0)
        self.assertEqual(audit['sourceFiles'],0)


if __name__=='__main__':
    unittest.main()
