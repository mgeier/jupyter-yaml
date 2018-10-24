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
        yield '  metadata: {\n'
        # TODO: write metadata, formatted as JSON, indented with 4 spaces
        yield '  }\n'
        # TODO: warning/error if there are unknown attributes
    yield 'metadata: {\n'
    # TODO: write metadata, formatted as JSON
    yield '}\n'
    # TODO: warning/error if there are unknown attributes


def from_yaml(lines):
    lines = iter(lines)
    nb = _nbformat.v4.new_notebook()
    line = None  # TODO: remove?
    try:
        line = next(lines)
        prefix, key, value = line.partition('nbformat: ')
        assert not prefix, prefix
        assert key
        nb.nbformat = int(value)
        assert nb.nbformat == 4
        line = next(lines)
        prefix, key, value = line.partition('nbformat_minor: ')
        assert not prefix, prefix
        assert key
        nb.nbformat_minor = int(value)
        line = next(lines)
        prefix, key, value = line.partition('cells:')
        assert not prefix, prefix
        assert key
        assert value == '\n'
    except StopIteration:
        # TODO: error, first three keys are required
        pass
    try:
        while True:
            line = next(lines)
            prefix, key, value = line.partition('- cell_type: ')
            if prefix:
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
                source = []
                for line in lines:
                    prefix, indent, source_line = line.partition('    ')
                    if prefix:
                        break
                    assert indent
                    source.append(source_line)
                else:
                    # TODO: error?
                    pass
                source = ''.join(source)
                assert source.endswith('\n')
                cell.source = source[:-1]
            else:
                # TODO: ???
                pass
            nb.cells.append(cell)
            line = next(lines)  # TODO: temporary, skip closing } of metadata
    except StopIteration:
        pass

    # TODO: check for metadata
    # TODO: check for unknown keys?
    # TODO: check validity?
    return nb


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
