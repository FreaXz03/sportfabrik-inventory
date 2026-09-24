"""Checks for source isolation and preservation of existing graph data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import projektwissen as knowledge


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patch = patch.object(knowledge, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / 'docs').mkdir()
        (self.root / 'docs/allowed.md').write_text('# Bestand\nText\n## Umlagerung\n`app/service.py`\n')
        (self.root / 'docs/private.md').write_text('PRIVATE_NOT_ALLOWED')
        (self.root / 'docs/wissensquellen.txt').write_text('docs/allowed.md\n')

    def test_index_preserves_original_and_excludes_unselected_text(self):
        graph = self.root / 'graphify-out/graph.json'
        graph.parent.mkdir()
        original = json.dumps({'nodes': [{'id': 'code', 'label': 'service',
                                          'source_file': 'app/service.py'}],
                               'links': [], 'directed': False, 'multigraph': False, 'graph': {}})
        graph.write_text(original)
        result, count = knowledge.index()
        content = result.read_text()
        self.assertEqual(graph.read_text(), original)
        self.assertEqual(count, 2)
        self.assertNotIn('PRIVATE_NOT_ALLOWED', content)
        self.assertIn('mentions_code_file', content)

    def test_rejects_traversal_and_symlinks_before_copy(self):
        selection = self.root / 'docs/wissensquellen.txt'
        for invalid in ('../private.md', '/tmp/private.md'):
            selection.write_text(invalid)
            with self.assertRaises(ValueError):
                knowledge.prepare_docs()
        (self.root / 'docs/link.md').symlink_to(self.root / 'docs/private.md')
        selection.write_text('docs/link.md')
        with self.assertRaises(ValueError):
            knowledge.prepare_docs()

    def test_prepare_removes_stale_inputs_preserves_semantic_output(self):
        with patch('builtins.print'):
            knowledge.prepare_docs()
        parent = self.root / 'graphify-out/selected-docs'
        (parent / 'input/old.md').write_text('OLD')
        (parent / 'graphify-out').mkdir()
        result = parent / 'graphify-out/graph.json'
        result.write_text('existing result')
        with patch('builtins.print'):
            knowledge.prepare_docs()
        self.assertFalse((parent / 'input/old.md').exists())
        self.assertFalse((parent / 'input/docs/private.md').exists())
        self.assertEqual(result.read_text(), 'existing result')

    def test_code_fences_are_not_document_sections(self):
        text = '# Real\n```python\n# Not a heading\n```\n## Next\nbody'
        self.assertEqual([s[3] for s in knowledge.sections(text)], ['Real', 'Next'])


if __name__ == '__main__':
    unittest.main()
