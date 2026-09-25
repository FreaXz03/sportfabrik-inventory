#!/usr/bin/env python3
"""Local, bounded Graphify lookup with an explicit Markdown source selection."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sources():
    result = []
    for raw in (ROOT / 'docs/wissensquellen.txt').read_text().splitlines():
        name = raw.strip()
        if not name or name.startswith('#'):
            continue
        relative = Path(name)
        path = ROOT / relative
        if (relative.is_absolute() or '..' in relative.parts
                or relative.parts[0] != 'docs' or relative.suffix != '.md'
                or path.resolve() != path.absolute() or not path.is_file()):
            raise ValueError(f'Ungueltige Dokumentquelle: {name}')
        if name not in result:
            result.append(name)
    return result


def output_dir(relative):
    path = ROOT / 'graphify-out' / relative
    if path.resolve() != path.absolute():
        raise ValueError('Ausgabeordner darf kein Symlink sein.')
    path.mkdir(parents=True, exist_ok=True)
    return path


def sections(text):
    lines = text.splitlines()
    starts = []
    fence = None
    for i, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        match = re.match(r'^(#{1,6})\s+(.+)', line) if fence is None else None
        if match:
            starts.append((i, len(match[1]), match[2]))
    for n, (start, level, title) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        yield start + 1, end, level, title, '\n'.join(lines[start + 1:end])


def index():
    code = ROOT / 'graphify-out/graph.json'
    if code.is_file():
        graph = json.loads(code.read_text())
    else:
        print('Hinweis: kein Codegraph vorhanden; nur Dokumentfundstellen.', file=sys.stderr)
        graph = {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': []}
    nodes = graph['nodes']
    links = graph.setdefault('links', graph.pop('edges', []))
    by_file = defaultdict(list)
    for node in nodes:
        by_file[node.get('source_file', '')].append(node['id'])
    count = 0
    for name in sources():
        parents = []
        for start, end, level, title, body in sections((ROOT / name).read_text()):
            node_id = f'doc::{name}::L{start}'
            nodes.append({'id': node_id, 'label': 'Doku: ' + title, 'file_type': 'document',
                          '_origin': 'local_heading_index', 'source_file': name,
                          'source_location': f'L{start}-L{end}',
                          'attributes': {'excerpt': ' '.join(body.split())[:320]}})
            while parents and parents[-1][0] >= level:
                parents.pop()
            if parents:
                links.append({'source': parents[-1][1], 'target': node_id,
                              'relation': 'contains_section', 'weight': 1})
            parents.append((level, node_id))
            for reference in set(re.findall(r'`((?:app|tests)/[^`\s]+\.(?:py|js|html|css))`', body)):
                # One representative symbol points into the existing code graph.
                if by_file.get(reference):
                    links.append({'source': node_id, 'target': by_file[reference][0],
                                  'relation': 'mentions_code_file', 'weight': 1})
            count += 1
    destination = output_dir('knowledge') / 'graph.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(graph, ensure_ascii=False))
    temporary.replace(destination)
    return destination, count


def prepare_docs():
    # Validate every source before touching the previous generated input.
    selected = sources()
    parent = output_dir('selected-docs')
    destination = parent / 'input'
    if destination.is_symlink():
        raise ValueError('Eingabeordner darf kein Symlink sein.')
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    # Ancestor graphifyignore excludes graphify-out; reset within this isolated corpus.
    (destination / '.graphifyignore').write_text('!*\n')
    for name in selected:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    print('Vorbereitet; keine KI aufgerufen:\n' + '\n'.join(selected))
    print(f'Eingabeordner: {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['index', 'query', 'prepare-docs'])
    parser.add_argument('question', nargs='?')
    args = parser.parse_args()
    if args.action == 'query' and not args.question:
        parser.error('query braucht einen Suchbegriff')
    if args.action == 'prepare-docs':
        prepare_docs()
        return
    path, count = index()
    if args.action == 'index':
        print(f'{count} Dokumentabschnitte mit Codegraph verbunden: {path}')
        return
    binary = shutil.which('graphify')
    if not binary:
        raise ValueError('Graphify nicht im PATH. Stattdessen gezielt mit rg suchen.')
    result = subprocess.run([binary, 'query', args.question, '--graph', str(path),
                             '--budget', '1200'], cwd=ROOT, check=False)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(f'Projektwissen: {error}', file=sys.stderr)
        raise SystemExit(1)
