import json as _json
import re as _re

import nbformat as _nbformat
import notebook.services.contents.filemanager as _fm

SUFFIX = '.jupyter'

# RegEx from nbformat JSON schema:
_RE_JSON = _re.compile('^application/(.*\\+)?json$')

# TODO: somehow use JSON schema? nbformat.validator.get_validator(4, 2)

# TODO: allow completely empty lines (or with fewer spaces than necessary)?


def generate_nonyaml_lines(nb):
    if nb.nbformat != 4:
        raise RuntimeError('Currently, only notebook version 4 is supported')
    yield _line('', 'nbformat', '4')
    yield _line('', 'nbformat_minor', nb.nbformat_minor)
    for cell in nb.cells:
        cell_type = cell.cell_type
        if cell_type == 'code' and cell.execution_count is not None:
            yield _line('', 'code', cell.execution_count)
        else:
            yield _line('', cell_type)
        yield from _prefixed_block('    ', cell.source)
        if cell.source == '' or cell.source.endswith('\n'):
            # NB: This additional \n has to be removed when reading
            yield '    \n'

        # NB: everything else is optional!

        if cell_type == 'markdown':
            # TODO: attachments (since v4.1)
            pass
        elif cell_type == 'code':
            for out in cell.outputs:
                yield from _code_cell_output(out)
        elif cell_type == 'raw':
            # TODO: attachments (since v4.1)
            pass
        else:
            raise RuntimeError('Unknown cell type: {!r}'.format(cell_type))
        if cell.metadata:
            yield from _json_block('  ', 'metadata', cell.metadata)
        # TODO: warning/error if there are unknown attributes
    if nb.metadata:
        yield from _json_block('', 'metadata', nb.metadata)
    # TODO: warning/error if there are unknown attributes


def to_nonyaml(nb):
    return ''.join(generate_nonyaml_lines(nb))


def from_nonyaml(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    Lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines" mode).

    If *source* is a list, line terminators may be omitted.

    """
    nb = _nbformat.v4.new_notebook()
    if isinstance(source, str):
        source = source.splitlines()
    lines = enumerate(source, start=1)
    try:
        i, line = next(lines)
        if line.rstrip() != 'nbformat 4':
            raise ParseError('First line must be exactly "nbformat 4"')
        i, line = next(lines)
        name, _, value = line.partition(' ')
        if name != 'nbformat_minor':
            raise ParseError('Second line must start with "nbformat_minor"')
    except StopIteration:
        raise ParseError('At least 2 lines are required')
    try:
        nb.nbformat_minor = int(value)
    except ValueError:
        raise ParseError(
            'Invalid value for "nbformat_minor": {!r}'.format(value), 2)

    blocks = []
    try:
        i, line = next(lines)
        while True:
            if line.startswith(' '):
                assert False, 'unexpected space'
            blocks.append([i, line.rstrip(), [], []])
            i, line = next(lines)
            while True:
                if line.startswith(' ' * 4):
                    line = line[4:-1 if line.endswith('\n') else None]
                elif not line.strip():
                    line = ''
                else:
                    break
                blocks[-1][2].append(line)
                i, line = next(lines)
            if line.startswith(' ' * 3):
                assert False, 'unexpected 3-space indentation'
            while True:
                if line.startswith(' ' * 2):
                    line = line[2:-1 if line.endswith('\n') else None]
                elif not line.strip():
                    line = ''
                else:
                    break
                blocks[-1][3].append(line)
                i, line = next(lines)
    except StopIteration:
        pass

    for i, name, source, data in blocks:
        pass

    # TODO: allow trailing empty lines


def from_nonyaml_old(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    In both cases, lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines" mode).

    """
    if isinstance(source, str):
        source = source.splitlines(keepends=True)
    lines = enumerate(source, start=1)
    nb = _nbformat.v4.new_notebook()
    try:
        no_match, _, value = next(lines)[1].partition('nbformat ')
        if no_match:
            # TODO: custom exception class? with line number
            raise ParseError('Expected "nbformat"', 1)
        nb.nbformat = int(value)
        # TODO: check for conversion errors
        if nb.nbformat != 4:
            raise ParseError('Only notebook version 4 is supported', 1)
        no_match, _, value = next(lines)[1].partition('nbformat_minor ')
        if no_match:
            raise ParseError('Expected "nbformat_minor"', 2)
        nb.nbformat_minor = int(value)
        # TODO: check for errors
    except StopIteration:
        raise ParseError(
            'At least 2 lines are required (nbformat/nbformat_minor)')
    try:
        line = next(lines)
        while True:
            if line[1].startswith('markdown'):
                tail = line[1][len('markdown'):].strip()
                if tail:
                    raise ParseError('No text allowed after "markdown"',
                                     line[0])
                cell = _nbformat.v4.new_markdown_cell()
            elif line[1].startswith('code'):
                cell = _nbformat.v4.new_code_cell()
                tail = line[1][len('code'):].strip()
                if tail:
                    cell.execution_count = int(tail)
                    # TODO: check for conversion errors?
            elif line[1].startswith('raw'):
                cell = _nbformat.v4.new_raw_cell()
                tail = line[1][len('raw'):].strip()
                if tail:
                    raise ParseError('No text allowed after "raw"', line[0])
            else:
                break

            source, line = _read_prefixed_block(lines, ' ' * 4)
            if source.endswith('\n'):
                # NB: This is the normal case, trailing \n is removed
                cell.source = source[:-1]
            else:
                # NB: This is illegal, but we tolerate it
                cell.source = source

            nb.cells.append(cell)

            # NB: Everything else is optional

            if cell.cell_type == 'markdown':
                # TODO: attachments
                pass
            elif cell.cell_type == 'code':
                # NB: Outputs are added to cell.outputs:
                line = _parse_outputs(line, lines, cell)
            elif cell.cell_type == 'raw':
                # TODO: attachments
                pass
            else:
                assert False

            if None in line:
                return nb  # EOF

            prefix, _, tail = line[1].partition('metadata')
            if prefix == '  ':
                if tail.strip():
                    raise ParseError('No text allowed after "metadata"',
                                     line[0])
                block, line = _read_prefixed_block(lines, ' ' * 4)
                cell.metadata = _json.loads(block)

            if None in line:
                return nb  # EOF
    except StopIteration:
        return nb  # EOF

    prefix, _, tail = line[1].partition('metadata')
    if prefix == '' and not tail.strip():
        block, line = _read_prefixed_block(lines, '  ')
        nb.metadata = _json.loads(block)

    # TODO: check for unknown keys?

    if None not in line:
        raise ParseError('Unexpected file content', line[0])
    return nb


class ParseError(Exception):

    def __str__(self):
        if len(self.args) == 2:
            return 'Line {0[1]}: {0[0]}'.format(self.args)
        return Exception.__str__(self)


def _line(prefix, key, value=None):
    if value is None:
        return '{}{}\n'.format(prefix, key)
    else:
        return '{}{} {}\n'.format(prefix, key, value)


def _code_cell_output(out):
    if out.output_type == 'stream':
        # TODO: can "name" be empty?
        yield _line('  ', 'stream', out.name)
        yield from _prefixed_block(' ' * 4, out.text)
    elif out.output_type in ('display_data', 'execute_result'):
        yield _line('  ', out.output_type)
        # TODO: check if out.execution_count matches cell.execution_count?
        # TODO: is "data" required? error message?
        if out.data:
            # TODO: sort MIME types?
            # TODO: alphabetically, by importance?
            # TODO: text-based formats first?
            for k, v in out.data.items():
                if _RE_JSON.match(k):
                    yield from _json_block('  ', '- ' + k, v)
                else:
                    yield from _text_block('  ', '- ' + k, v)
        # TODO: metadata
    elif out.output_type == 'error':
        yield _line('  ', out.output_type)
        yield _line('  - ', 'ename')
        yield from _prefixed_block(' ' * 4, out.ename)
        yield _line('  - ', 'evalue')
        yield from _prefixed_block(' ' * 4, out.evalue)
        yield _line('  - ', 'traceback')
        # NB: Traceback lines don't seem to be \n-terminated,
        #     but they may contain \n characters in the middle!
        separator = ''
        for frame in out.traceback:
            if separator:
                yield separator
            else:
                separator = '   ~\n'
            for line in frame.splitlines():
                yield '    ' + line + '\n'
    else:
        raise RuntimeError('Unknown output type: {!r}'.format(out.output_type))


def _read_traceback(lines):
    traceback = []
    while True:
        frame, line = _read_prefixed_block(lines, ' ' * 4)
        if frame.endswith('\n'):
            # This is the normal case
            frame = frame[:-1]
        traceback.append(frame)
        no_match, _, tail = line[1].partition('   ~')
        if no_match:
            break
        if tail.strip():
            raise ParseError('No text allowed after "~"', line[0])
    return traceback, line


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
        nr, line = None, None
    return ''.join(block), (nr, line)


def _text_block(prefix, key, value):
    yield '{}{}\n'.format(prefix, key)
    yield from _prefixed_block(prefix + '  ', value)


def _json_block(prefix, key, value):
    yield '{}{}\n'.format(prefix, key)
    yield from _prefixed_block(prefix + '  ', _serialize_json(value))


def _serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    return _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)


def _parse_outputs(line, lines, cell):
    # Outputs are added to cell.outputs, StopIteration may happen any time
    cell.outputs = []
    while True:
        if not line[1].startswith('  '):
            break

        out = {}
        cell.outputs.append(out)

        output_type = line[1][2:].rstrip()
        out['output_type'] = output_type
        if output_type.startswith('stream'):
            if output_type[6] != ' ':
                raise ParseError('Expected "stream stdout" or "stream stderr"',
                                 line[0])
            out['output_type'] = 'stream'
            out['name'] = output_type[7:].lstrip(' ')
            text, line = _read_prefixed_block(lines, ' ' * 4)
            # TODO: no \n has to be removed?
            out['text'] = text
        elif output_type in ('display_data', 'execute_result'):
            if output_type == 'execute_result':
                out['execution_count'] = cell.execution_count
            out['data'] = {}
            line = next(lines)
            while True:
                if not line[1].startswith('  - '):
                    break
                mime_type = line[1][4:].rstrip()
                if mime_type == 'metadata':
                    # TODO: read metadata
                    raise ParseError('TODO: implement output "metadata"',
                                     line[0])
                data, line = _read_prefixed_block(lines, ' ' * 4)

                # TODO: remove trailing \n?

                if _RE_JSON.match(mime_type):
                    data = _json.loads(data)
                out['data'][mime_type] = data
        elif output_type == 'error':
            # NB: All fields are required
            line = next(lines)
            if line[1].rstrip() != '  - ename':
                raise ParseError('Expected "  - ename"', line[0])
            out['ename'], line = _read_prefixed_block(lines, ' ' * 4)
            if line[1].rstrip() != '  - evalue':
                raise ParseError('Expected "  - evalue"', line[0])
            out['evalue'], line = _read_prefixed_block(lines, ' ' * 4)
            if line[1].rstrip() != '  - traceback':
                raise ParseError('Expected "  - traceback"', line[0])
            out['traceback'], line = _read_traceback(lines)
        else:
            raise ParseError('Unknown output type: {!r}'.format(output_type),
                             line[0])
    return line


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
                return from_nonyaml(f)
            except Exception as e:
                raise _fm.web.HTTPError(400, str(e))

    def _save_notebook(self, os_path, nb):
        if not os_path.endswith(SUFFIX):
            return super()._save_notebook(os_path, nb)

        # TODO: raise proper exception on error?
        with self.atomic_writing(os_path, text=True,
                                 newline=None,  # "universal newlines"
                                 encoding='utf-8') as f:
            f.writelines(generate_nonyaml_lines(nb))
