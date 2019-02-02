"""Serialize and deserialize Jupyter format."""
import json as _json
import re as _re

import nbformat as _nbformat

SUFFIX = '.jupyter'
_TERMINATOR = 'the end'

# RegEx from nbformat JSON schema:
_RE_JSON = _re.compile('^application/(.*\\+)?json$')

# TODO: somehow use JSON schema? nbformat.validator.get_validator(4, 2)


def generate_lines(nb):
    if nb.nbformat != 4:
        raise RuntimeError('Currently, only notebook version 4 is supported')
    yield _line('', 'nbformat', nb.nbformat)
    yield _line('', 'nbformat_minor', nb.nbformat_minor)
    for cell in nb.cells:
        cell_type = cell.cell_type
        if cell_type == 'code' and cell.execution_count is not None:
            yield _line('', 'code', cell.execution_count)
        else:
            yield _line('', cell_type)
        yield from _indented_block(cell.source + '\n')

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
            yield from _json_block('  metadata', cell.metadata)
        # TODO: warning/error if there are unknown attributes
    if nb.metadata:
        yield from _json_block('metadata', nb.metadata)
    # TODO: warning/error if there are unknown attributes


def serialize(nb):
    return ''.join(generate_lines(nb))


def deserialize(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    Lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines" mode).

    If *source* is a list, line terminators may be omitted.

    """
    if isinstance(source, str):
        source = source.splitlines()
    nb = _nbformat.v4.new_notebook()
    parser = _get_parser(nb)
    i = 0
    try:
        parser.send(None)
        for i, line in enumerate(source, start=1):
            if line.endswith('\n'):
                line = line[:-1]
            parser.send(line)
        i += 1
        parser.send(_TERMINATOR)
    except ParseError as e:
        if len(e.args) == 1:
            # Add line number
            e.args += i,
        elif len(e.args) == 2:
            # Apply line number offset
            e.args = e.args[0], i - e.args[1]
        raise e
    except Exception as e:
        raise ParseError(type(e).__name__ + ': ' + str(e), i)
    finally:
        parser.close()
    return nb


def _get_parser(nb):
    nb.nbformat = yield from _parse_nbformat()
    nb.nbformat_minor = yield from _parse_nbformat_minor()
    nb.cells, line = yield from _parse_cells()
    nb.metadata, line = yield from _parse_notebook_metadata(line)
    yield from _parse_excess_lines(line)
    assert False, 'This is never reached'


def _parse_nbformat():
    line = yield
    nbformat = _check_word_plus_integer(line, 'nbformat')
    if nbformat != 4:
        raise ParseError('Only v4 notebooks are currently supported')
    return nbformat


def _parse_nbformat_minor():
    line = yield
    return _check_word_plus_integer(line, 'nbformat_minor')


def _parse_cells():
    cells = []
    line = yield
    while True:
        if _check_word(line, 'markdown'):
            cell = _nbformat.v4.new_markdown_cell()
        elif line.startswith('code'):
            cell = _nbformat.v4.new_code_cell()
            if line not in ('code', 'code '):
                cell.execution_count = _check_word_plus_integer(
                    line, 'code')
        elif _check_word(line, 'raw'):
            cell = _nbformat.v4.new_raw_cell()
        else:
            break
        cell.source, line = yield from _parse_indented_lines()
        if cell.cell_type in ('markdown', 'raw'):
            # TODO: parse attachments
            # TODO: attachments (since v4.1)
            #yield from _parse_???(line)
            pass
        elif cell.cell_type == 'code':
            cell.outputs, line = yield from _parse_code_outputs(
                cell.execution_count, line)
        if line.startswith('  ') and _check_word('metadata', line[2:]):
            metadata, line = yield from _parse_metadata()
            cell.metadata = metadata
        cells.append(cell)
    return cells, line


def _parse_code_outputs(execution_count, line):
    outputs = []
    while True:
        out = None
        if not line.startswith('  '):
            break
        if line.startswith(' ' * 3):
            raise ParseError('Invalid indentation')
        output_type = line[2:]
        kwargs = {}
        if output_type.startswith('stream'):
            if len(output_type) < 7 or output_type[6] != ' ':
                raise ParseError('Expected stream type')
            # NB: "name" is required!
            # TODO: check if name is valid?
            kwargs['name'] = output_type[7:]
            text, line = yield from _parse_indented_lines()
            kwargs['text'] = text
            out = _nbformat.v4.new_output('stream', **kwargs)
        elif (_check_word('display_data', output_type) or
                _check_word('execute_result', output_type)):
            if output_type == 'execute_result':
                kwargs['execution_count'] = execution_count
            kwargs['data'], line = yield from _parse_output_data()
            # TODO: output metadata ("  - metadata")
            out = _nbformat.v4.new_output(output_type, **kwargs)
        elif _check_word('error', output_type):
            line = yield
            # NB: All fields are required
            if line != '  - ename':
                raise ParseError("Expected '  - ename'")
            kwargs['ename'], line = yield from _parse_indented_lines()
            if line != '  - evalue':
                raise ParseError("Expected '  - evalue'")
            kwargs['evalue'], line = yield from _parse_indented_lines()
            if line != '  - traceback':
                raise ParseError("Expected '  - traceback'")
            kwargs['traceback'], line = yield from _parse_traceback()
            out = _nbformat.v4.new_output('error', **kwargs)
        elif output_type.startswith('metadata'):
            break
        else:
            raise ParseError("Expected cell output or 'metadata'")
        outputs.append(out)
    return outputs, line


def _parse_output_data():
    data = {}
    line = yield
    while True:
        if not line.startswith('  - '):
            break
        mime_type = line[4:]
        # TODO: move check to _parse_output_metadata
        if mime_type.strip() == 'metadata':
            break
        # TODO: move check to _parse_output_metadata
        if mime_type != mime_type.strip():
            raise ParseError('Invalid MIME type: {!r}'.format(mime_type))
        # TODO: check for valid MIME type?
        content, line = yield from _parse_indented_lines(trailing_newline=True)
        if _RE_JSON.match(mime_type):
            data[mime_type] = _parse_json(content)
        else:
            if content and content.endswith('\n') and content.strip('\n'):
                content = content[:-1]
            data[mime_type] = content
    return data, line


def _parse_traceback():
    traceback = []
    while True:
        frame, line = yield from _parse_indented_lines()
        assert not frame.endswith('\n')
        traceback.append(frame)
        no_match, _, tail = line.partition('   ~')
        if no_match:
            break
        if tail.strip():
            raise ParseError("No text allowed after '~'")
    return traceback, line


def _parse_indented_lines(trailing_newline=False):
    lines = []
    while True:
        line = yield
        if line.startswith(' ' * 4):
            line = line[4:]
        elif not line.strip():
            line = ''  # Blank line
        else:
            break
        lines.append(line)
    if not lines:
        return '', line
    text = '\n'.join(lines)
    if trailing_newline:
        text += '\n'
    return text, line


def _parse_metadata():
    text, line = yield from _parse_indented_lines()
    return _parse_json(text), line


def _parse_notebook_metadata(line):
    if line == _TERMINATOR:
        return {}, line
    if _check_word('metadata', line):
        metadata, line = yield from _parse_metadata()
        return metadata, line
    raise ParseError(
        "Expected (unindented) cell type or 'metadata', got {!r}".format(line))


def _parse_excess_lines(line):
    if line != _TERMINATOR:
        raise ParseError(
            'All notebook metadata lines must be indented by 4 spaces '
            'and no additional lines are allowed')
    yield  # If all goes well, execution stops here
    raise ParseError('Illegal content', 1)


def _check_word_plus_integer(line, word):
    if line is None:
        line = ''
    m = _re.match(word + ' ([0-9]|[1-9][0-9]+)$', line)
    if not m:
        raise ParseError(
            'Expected {!r} followed by a space and an integer'.format(word))
    return int(m.group(1))


def _check_word(line, word):
    if line.startswith(word):
        if line != word:
            raise ParseError('No text allowed after {!r}'.format(word))
        return True
    else:
        return False


def _parse_json(text):
    if not text:
        return {}
    try:
        data = _json.loads(text)
    except _json.JSONDecodeError as e:
        # Abuse JSONDecodeError constructor to calculate number of lines:
        total = _json.JSONDecodeError('', text, -1).lineno
        raise ParseError(
            'JSON error in column {}: {}'.format(e.colno + 4, e.msg),
            total - e.lineno + 1)
    return data


class ParseError(Exception):

    def __str__(self):
        if len(self.args) == 2:
            return 'Line {1}: {0}'.format(*self.args)
        return super().__str__()


def _line(prefix, key, value=None):
    if value is None:
        return '{}{}\n'.format(prefix, key)
    else:
        return '{}{} {}\n'.format(prefix, key, value)


def _code_cell_output(out):
    if out.output_type == 'stream':
        # TODO: can "name" be empty?
        yield _line('  ', 'stream', out.name)
        yield from _indented_block(out.text)
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
                    yield from _json_block('  - ' + k, v)
                else:
                    if v.endswith('\n') and v.strip('\n'):
                        v += '\n'
                    yield from _text_block('  - ' + k, v)
        # TODO: metadata
    elif out.output_type == 'error':
        yield _line('  ', out.output_type)
        yield _line('  - ', 'ename')
        yield from _indented_block(out.ename)
        yield _line('  - ', 'evalue')
        yield from _indented_block(out.evalue)
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


def _indented_block(text):
    for line in text.splitlines():
        yield ' ' * 4 + line + '\n'


def _text_block(key, value):
    yield key + '\n'
    yield from _indented_block(value)


def _json_block(key, value):
    yield key + '\n'
    yield from _indented_block(_serialize_json(value))


def _serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    return _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
