import json as _json

import nbformat as _nbformat
import notebook.services.contents.filemanager as _fm

SUFFIX = '.jupyter'


# TODO: somehow use JSON schema? nbformat.validator.get_validator(4, 2)

# TODO: allow completely empty lines (or with fewer spaces than necessary)?


def generate_yaml_lines(nb):
    if nb.nbformat != 4:
        raise RuntimeError('Currently, only notebook version 4 is supported')
    yield _line('', 'nbformat', '4')
    yield _line('', 'nbformat_minor', nb.nbformat_minor)
    yield _line('', 'cells')
    for cell in nb.cells:
        yield _line('- ', 'cell_type', cell.cell_type)
        if cell.cell_type == 'code' and cell.execution_count is not None:
            yield _line('  ', 'execution_count', cell.execution_count)
        yield from _text_block('  ', 'source', cell.source)
        if cell.source == '' or cell.source.endswith('\n'):
            # NB: This additional \n has to be removed when reading
            yield '    \n'

        # NB: everything else is optional!

        if cell.cell_type == 'markdown':
            # TODO: attachments (since v4.1)
            pass
        elif cell.cell_type == 'code':
            if cell.outputs:
                yield _line('  ', 'outputs')
                for out in cell.outputs:
                    yield from _code_cell_output(out)
        elif cell.cell_type == 'raw':
            # TODO: attachments (since v4.1)
            pass
        else:
            raise RuntimeError(
                'Unknown cell type: {!r}'.format(cell.cell_type))

        if cell.metadata:
            yield from _json_block('  ', 'metadata', cell.metadata)
        # TODO: warning/error if there are unknown attributes
    if nb.metadata:
        yield from _json_block('', 'metadata', nb.metadata)
    # TODO: warning/error if there are unknown attributes


def to_yaml(nb):
    return ''.join(generate_yaml_lines(nb))


def from_yaml(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    In both cases, lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines").

    """
    if isinstance(source, str):
        source = source.splitlines(keepends=True)
    lines = enumerate(source, start=1)
    nb = _nbformat.v4.new_notebook()
    try:
        no_match, _, value = next(lines)[1].partition('nbformat: ')
        if no_match:
            # TODO: custom exception class?
            raise RuntimeError('First line must specify "nbformat"')
        nb.nbformat = int(value)
        # TODO: check for errors
        assert nb.nbformat == 4
        no_match, _, value = next(lines)[1].partition('nbformat_minor: ')
        if no_match:
            raise RuntimeError('Second line must specify "nbformat_minor"')
        # TODO: check for errors
        nb.nbformat_minor = int(value)
        line = next(lines)
        if line[1] != 'cells:\n':
            raise RuntimeError('Third line must contain "cells:"')
    except StopIteration:
        raise RuntimeError('Too few lines')
    try:
        line = next(lines)
        while True:
            no_match, _, cell_type = line[1].partition('- cell_type: ')
            if no_match:
                break
            assert _
            line = next(lines)
            if cell_type == 'markdown\n':
                cell = _nbformat.v4.new_markdown_cell()
            elif cell_type == 'code\n':
                cell = _nbformat.v4.new_code_cell()
                prefix = '  execution_count: '
                if line[1].startswith(prefix):
                    # TODO: check for errors?
                    cell.execution_count = int(line[1][len(prefix):])
                    line = next(lines)
            else:
                raise RuntimeError(
                    'Line {}: Unknown cell type: {!r}'.format(line[0] - 1, cell_type.rstrip('\n')))
            if line[1] == '  source: |+2\n':
                source, line = _read_prefixed_block(lines, ' ' * 4)
                assert source.endswith('\n')
                cell.source = source[:-1]
            else:
                # TODO: ???
                assert False

            # TODO: check cell_type again!

            if line[1] == '  outputs:\n':
                cell.outputs = []
                line = next(lines)
                while True:
                    out = {}
                    prefix = '  - output_type: '
                    if line[1].startswith(prefix):
                        assert line[1].endswith('\n')
                        out['output_type'] = line[1][len(prefix):-1]
                    else:
                        break
                    cell.outputs.append(out)
                    line = next(lines)

                    # TODO: different things depending on output_type

                    if out['output_type'] == 'stream':
                        # TODO name and text are required!
                        prefix = '    name: '
                        if line[1].startswith(prefix):
                            assert line[1].endswith('\n')
                            out['name'] = line[1][len(prefix):-1]
                        line = next(lines)
                        if line[1] == '    text: |+2\n':
                            text, line = _read_prefixed_block(lines, ' ' * 6)
                            # TODO: no \n has to be removed?
                            out['text'] = text
                    elif out['output_type'] in ('display_data',
                                                'execute_result'):
                        if out['output_type'] == 'execute_result':
                            prefix = '    execution_count: '
                            if line[1].startswith(prefix):
                                assert line[1].endswith('\n')
                                out['execution_count'] = int(line[1][len(prefix):-1])
                                line = next(lines)
                        if line[1] == '    data:\n':
                            out['data'] = {}
                            line = next(lines)
                            while True:
                                if line[1].startswith(' ' * 6):
                                    suffix = ': |+2\n'
                                    if not line[1].endswith(suffix):
                                        suffix = ':\n'
                                        if not line[1].endswith(suffix):
                                            raise RuntimeError('TODO')
                                    mime_type = line[1][6:-len(suffix)]
                                    # TODO: is bytes allowed?
                                    data, line = _read_prefixed_block(
                                        lines, ' ' * 8)
                                    # TODO: remove trailing \n?

                                    # TODO: better check?
                                    if suffix == ':\n':
                                        data = _json.loads(data)
                                    out['data'][mime_type] = data
                                else:
                                    break
                        else:
                            break

                        # TODO: read metadata

                    elif out['output_type'] == 'error':
                        # TODO: all fields are required
                        prefix = '    ename: '
                        if line[1].startswith(prefix):
                            assert line[1].endswith('\n')
                            out['ename'] = line[1][len(prefix):-1]
                            line = next(lines)
                        if line[1] == '    evalue: |+2\n':
                            value, line = _read_prefixed_block(lines, ' ' * 6)
                            # TODO: last \n has to be removed?
                            out['evalue'] = value
                        if line[1] == '    traceback: |+2\n':
                            tb, line = _read_prefixed_block(lines, ' ' * 6)
                            out['traceback'] = tb.splitlines()
            if line[1] is None:
                break  # EOF
            if line[1] == '  metadata:\n':
                block, line = _read_prefixed_block(lines, '    ')
                cell.metadata = _json.loads(block)
            nb.cells.append(cell)
            if line[1] is None:
                break  # EOF
    except StopIteration:
        line = None, None  # No cells, no metadata

    if line[1] == 'metadata:\n':
        block, line = _read_prefixed_block(lines, '  ')
        nb.metadata = _json.loads(block)

    # TODO: check for unknown keys?

    assert line[1] is None, repr(line)

    # TODO: generator must be exhausted

    # TODO: check validity?
    return nb


def _line(prefix, key, value=None):
    if value is None:
        return '{}{}:\n'.format(prefix, key)
    else:
        return '{}{}: {}\n'.format(prefix, key, value)


def _code_cell_output(out):
    yield _line('  - ', 'output_type', out.output_type)
    if out.output_type == 'stream':
        yield _line(' ' * 4, 'name', out.name)
        yield from _text_block(' ' * 4, 'text', out.text)
    elif out.output_type in ('display_data', 'execute_result'):
        if (out.output_type == 'execute_result'
                and out.execution_count is not None):
            yield _line(' ' * 4, 'execution_count', out.execution_count)
        # TODO: is "data" required? error message?
        if out.data:
            yield _line(' ' * 4, 'data')
            # TODO: sort MIME types?
            # TODO: alphabetically, by importance?
            # TODO: text-based formats first?
            for k, v in out.data.items():
                # TODO: how does nbformat differentiate?
                if k.endswith('json'):
                    yield from _json_block(' ' * 6, k, v)
                else:
                    yield from _text_block(' ' * 6, k, v)
        # TODO: metadata
    elif out.output_type == 'error':
        yield _line(' ' * 4, 'ename', out.ename)
        yield from _text_block(' ' * 4, 'evalue', out.evalue)
        # NB: Traceback lines don't seem to be \n-terminated,
        #     but they may contain \n in the middle!
        tb = '\n'.join(out.traceback)
        yield from _text_block(' ' * 4, 'traceback', tb)
        # TODO: remove this, just to be safe:
        assert not tb.endswith('\n')
    else:
        raise RuntimeError('Unknown output type: {!r}'.format(out.output_type))


def _prefixed_block(prefix, text):
    for line in text.splitlines():
        yield prefix + line + '\n'


def _read_prefixed_block(lines, prefix):
    block = []
    for nr, line in lines:
        no_match, _, block_line = line.partition(prefix)
        if no_match:
            break
        assert _ == prefix
        block.append(block_line)
    else:
        line = None
    return ''.join(block), (nr, line)


def _text_block(prefix, key, value):
    yield '{}{}: |+2\n'.format(prefix, key)
    yield from _prefixed_block(prefix + '  ', value)


def _json_block(prefix, key, value):
    yield '{}{}:\n'.format(prefix, key)
    yield from _prefixed_block(prefix + '  ', _serialize_json(value))


def _serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    return _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)


class FileContentsManager(_fm.FileContentsManager):

    def get(self, path, content=True, type=None, format=None):
        if type is None and path.endswith(SUFFIX):
            type = 'notebook'
        return super().get(path, content, type, format)

    def _read_notebook(self, os_path, as_version=4):
        if not os_path.endswith(SUFFIX):
            return super()._read_notebook(os_path, as_version)

        with self.open(os_path, 'r', encoding='utf-8', newline=None) as f:
            try:
                assert as_version == 4
                return from_yaml(f)
            except Exception as e:
                raise _fm.web.HTTPError(400, str(e))

    def _save_notebook(self, os_path, nb):
        if not os_path.endswith(SUFFIX):
            return super()._save_notebook(os_path, nb)

        # TODO: raise proper exception on error?
        with self.atomic_writing(os_path, text=True,
                                 newline=None,  # "universal newlines"
                                 encoding='utf-8') as f:
            f.writelines(generate_yaml_lines(nb))
