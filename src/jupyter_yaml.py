import json as _json

import nbformat as _nbformat
from notebook.services.contents.filemanager import FileContentsManager as _CM

SUFFIX = '.jupyter'


# TODO: somehow use JSON schema? nbformat.validator.get_validator(4, 2)

# TODO: allow completely empty lines (or with fewer spaces than necessary)?


def generate_yaml_lines(nb):
    assert nb.nbformat == 4
    yield 'nbformat: 4\n'
    yield 'nbformat_minor: {}\n'.format(nb.nbformat_minor)
    yield 'cells:\n'
    for cell in nb.cells:
        # TODO: error if cell type is unknown
        yield '- cell_type: {}\n'.format(cell.cell_type)
        if cell.cell_type == 'code' and cell.execution_count is not None:
            yield '  execution_count: {}\n'.format(cell.execution_count)
        yield '  source: |+2\n'
        yield from _prefixed_block(cell.source, ' ' * 4)

        # NB: everything else is optional!

        if cell.cell_type == 'markdown':
            # TODO: attachments (since v4.1)
            pass
        elif cell.cell_type == 'code':
            if cell.outputs:
                yield '  outputs:\n'
                for out in cell.outputs:
                    yield '  - output_type: {}\n'.format(out.output_type)
                    if out.output_type == 'stream':
                        yield '    name: {}\n'.format(out.name)
                        yield '    text: |+2\n'
                        yield from _prefixed_block(
                            out.text, ' ' * 6, add_newline=False)
                    elif out.output_type in ('display_data', 'execute_result'):
                        if (out.output_type == 'execute_result'
                                and out.execution_count is not None):
                            yield '    execution_count: {}\n'.format(
                                out.execution_count)
                        if out.data:
                            yield '    data:\n'
                            # TODO: sort MIME types?
                            # TODO: alphabetically, by importance?
                            # TODO: text-based formats first?
                            for k, v in out.data.items():
                                # TODO: how does nbformat differentiate?
                                if k.endswith('json'):
                                    yield '      {}:\n'.format(k)
                                    yield from _prefixed_block(
                                        _serialize_json(v), ' ' * 8)
                                else:
                                    yield '      {}: |+2\n'.format(k)
                                    yield from _prefixed_block(v, ' ' * 8)
                        # TODO: metadata
                        pass
                    elif out.output_type == 'error':
                        yield '    ename: {}\n'.format(out.ename)
                        yield '    evalue: |+2\n'
                        yield from _prefixed_block(out.evalue, ' ' * 6)
                        # NB: Traceback lines don't seem to be \n-terminated,
                        #     but they may contain \n in the middle!
                        yield '    traceback: |+2\n'
                        tb = '\n'.join(out.traceback)
                        yield from _prefixed_block(tb, ' ' * 6)
                    else:
                        assert False
        elif cell.cell_type == 'raw':
            # TODO: attachments (since v4.1)
            pass
        else:
            # TODO: unknown cell type
            assert False

        if cell.metadata:
            yield '  metadata:\n'
            yield from _prefixed_block(_serialize_json(cell.metadata), ' ' * 4)
        # TODO: warning/error if there are unknown attributes
    yield 'metadata:\n'
    if nb.metadata:
        yield from _prefixed_block(_serialize_json(nb.metadata), ' ' * 2)
    # TODO: warning/error if there are unknown attributes


def _serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    return _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)


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
        no_match, _, value = next(lines).partition('nbformat: ')
        assert not no_match, no_match
        assert _
        nb.nbformat = int(value)
        assert nb.nbformat == 4
        no_match, _, value = next(lines).partition('nbformat_minor: ')
        assert not no_match, no_match
        assert _
        nb.nbformat_minor = int(value)
        no_match, _, value = next(lines).partition('cells:')
        assert not no_match, no_match
        assert _
        assert value == '\n'
    except StopIteration:
        # TODO: error, first three keys are required
        assert False
    try:
        line = next(lines)
        while True:
            no_match, _, cell_type = line.partition('- cell_type: ')
            if no_match:
                break
            assert _
            line = next(lines)
            if cell_type == 'markdown\n':
                cell = _nbformat.v4.new_markdown_cell()
            elif cell_type == 'code\n':
                cell = _nbformat.v4.new_code_cell()
                prefix = '  execution_count: '
                if line.startswith(prefix):
                    # TODO: check for errors?
                    cell.execution_count = int(line[len(prefix):])
                    line = next(lines)
            else:
                # TODO
                assert False
            if line == '  source: |+2\n':
                source, line = _read_prefixed_block(lines, '    ')
                assert source.endswith('\n')
                cell.source = source[:-1]
            else:
                # TODO: ???
                assert False

            # TODO: check cell_type again!

            if line == '  outputs:\n':
                cell.outputs = []
                line = next(lines)
                while True:
                    out = {}
                    prefix = '  - output_type: '
                    if line.startswith(prefix):
                        assert line.endswith('\n')
                        out['output_type'] = line[len(prefix):-1]
                    else:
                        break
                    cell.outputs.append(out)
                    line = next(lines)

                    # TODO: different things depending on output_type

                    if out['output_type'] == 'stream':
                        # TODO name and text are required!
                        prefix = '    name: '
                        if line.startswith(prefix):
                            assert line.endswith('\n')
                            out['name'] = line[len(prefix):-1]
                        line = next(lines)
                        if line == '    text: |+2\n':
                            text, line = _read_prefixed_block(lines, ' ' * 6)
                            # TODO: no \n has to be removed?
                            out['text'] = text
                    elif out['output_type'] in ('display_data',
                                                'execute_result'):
                        if out['output_type'] == 'execute_result':
                            prefix = '    execution_count: '
                            if line.startswith(prefix):
                                assert line.endswith('\n')
                                out['execution_count'] = int(line[len(prefix):-1])
                                line = next(lines)
                        if line == '    data:\n':
                            out['data'] = {}
                            line = next(lines)
                            while True:
                                if line.startswith(' ' * 6):
                                    suffix = ': |+2\n'
                                    # TODO: if endwith suffix -> str
                                    # TODO: if endswith ':\n' -> JSON dict
                                    # TODO: is bytes allowed?
                                    assert line.endswith(suffix)
                                    mime_type = line[6:-len(suffix)]
                                    data, line = _read_prefixed_block(
                                        lines, ' ' * 8)
                                    # TODO: remove trailing \n?
                                    out['data'][mime_type] = data
                                else:
                                    break
                        else:
                            break

                        # TODO: read metadata

                    elif out['output_type'] == 'error':
                        # TODO: all fields are required
                        prefix = '    ename: '
                        if line.startswith(prefix):
                            assert line.endswith('\n')
                            out['ename'] = line[len(prefix):-1]
                            line = next(lines)
                        if line == '    evalue: |+2\n':
                            value, line = _read_prefixed_block(lines, ' ' * 6)
                            # TODO: last \n has to be removed?
                            out['evalue'] = value
                        if line == '    traceback: |+2\n':
                            tb, line = _read_prefixed_block(lines, ' ' * 6)
                            out['traceback'] = tb.splitlines()
            if line is None:
                break  # EOF
            if line == '  metadata:\n':
                block, line = _read_prefixed_block(lines, '    ')
                cell.metadata = _json.loads(block)
            nb.cells.append(cell)
            if line is None:
                break  # EOF
    except StopIteration:
        line = None  # No cells, no metadata

    if line == 'metadata:\n':
        block, line = _read_prefixed_block(lines, '  ')
        nb.metadata = _json.loads(block)

    # TODO: check for unknown keys?

    assert line is None, repr(line)

    # TODO: generator must be exhausted

    # TODO: check validity?
    return nb


def _prefixed_block(text, prefix, add_newline=True):
    for line in text.splitlines(keepends=True):
        yield prefix
        yield line
    if add_newline:
        if not text or line.endswith('\n'):
            yield '    '
        yield '\n'  # NB: This additional \n has to be removed when reading


def _read_prefixed_block(lines, prefix):
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
