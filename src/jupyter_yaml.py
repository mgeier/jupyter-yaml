import json as _json

import nbformat as _nbformat
from notebook.services.contents.filemanager import FileContentsManager as _CM

SUFFIX = '.jupyter'


def generate_yaml_lines(nb):
    assert nb.nbformat == 4
    yield 'nbformat: 4\n'
    yield 'nbformat_minor: {}\n'.format(nb.nbformat_minor)
    yield 'cells:\n'
    for cell in nb.cells:
        # TODO: error if cell type is unknown
        yield '- cell_type: {}\n'.format(cell.cell_type)
        yield '  source: |+2\n'
        for line in cell.source.splitlines(keepends=True):
            yield '    '
            yield line
        if not cell.source or line.endswith('\n'):
            yield '    '
        # NB: This additional \n has to be removed when reading
        yield '\n'
        # TODO: write outputs if present
        # TODO: write execution_count if present
        if cell.metadata:
            yield '  metadata:\n'
            for line in serialize_json(cell.metadata):
                yield '    '
                yield line
            yield '\n'
        # TODO: warning/error if there are unknown attributes
    yield 'metadata:\n'
    if nb.metadata:
        for line in serialize_json(nb.metadata):
            yield '  '
            yield line
        yield '\n'
    # TODO: warning/error if there are unknown attributes


def serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    s = _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    yield from s.splitlines(keepends=True)


def from_yaml(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    In both cases, lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines").

    """
    if isinstance(source, str):
        source = source.splitlines(keepends=True)
    lines = iter(source)
    nb = _nbformat.v4.new_notebook()
    try:
        no_match, key, value = next(lines).partition('nbformat: ')
        assert not no_match, no_match
        assert key
        nb.nbformat = int(value)
        assert nb.nbformat == 4
        no_match, key, value = next(lines).partition('nbformat_minor: ')
        assert not no_match, no_match
        assert key
        nb.nbformat_minor = int(value)
        no_match, key, value = next(lines).partition('cells:')
        assert not no_match, no_match
        assert key
        assert value == '\n'
    except StopIteration:
        # TODO: error, first three keys are required
        assert False
    try:
        line = next(lines)
        while True:
            no_match, key, value = line.partition('- cell_type: ')
            if no_match:
                break
            assert key
            if value == 'markdown\n':
                cell = _nbformat.v4.new_markdown_cell()
            elif value == 'code\n':
                cell = _nbformat.v4.new_code_cell()
            else:
                # TODO
                assert False
            line = next(lines)
            if line == '  source: |+2\n':
                source, line = _get_prefixed_block(lines, '    ')
                assert source.endswith('\n')
                cell.source = source[:-1]
            else:
                # TODO: ???
                assert False
            if line is None:
                break  # EOF
            if line == '  metadata:\n':
                block, line = _get_prefixed_block(lines, '    ')
                cell.metadata = _json.loads(block)
            nb.cells.append(cell)
            if line is None:
                break  # EOF
    except StopIteration:
        line = None  # No cells, no metadata

    if line == 'metadata:\n':
        block, line = _get_prefixed_block(lines, '  ')
        nb.metadata = _json.loads(block)

    # TODO: check for unknown keys?

    assert line is None

    # TODO: generator must be exhausted

    # TODO: check validity?
    return nb


def _get_prefixed_block(lines, prefix):
    block = []
    for line in lines:
        no_match, _, block_line = line.partition(prefix)
        if no_match:
            break
        assert _ == prefix
        block.append(block_line)
    else:
        line = None
    return ''.join(block), line


class FileContentsManager(_CM):

    def get(self, path, content=True, type=None, format=None):
        if type is None and path.endswith(SUFFIX):
            type = 'notebook'
        return _CM.get(self, path, content, type, format)

    def _read_notebook(self, os_path, as_version=4):
        if not os_path.endswith(SUFFIX):
            return _CM._read_notebook(self, os_path, as_version)

        assert as_version == 4

        # TODO: catch exceptions, raise HTTPError?
        with self.open(os_path, 'r', encoding='utf-8', newline=None) as f:
            return from_yaml(f)

    def _save_notebook(self, os_path, nb):
        if not os_path.endswith(SUFFIX):
            return _CM._save_notebook(self, os_path, nb)

        # TODO: raise proper exception on error?
        with self.atomic_writing(os_path, text=True,
                                 newline=None,  # "universal newlines"
                                 encoding='utf-8') as f:
            f.writelines(generate_yaml_lines(nb))
