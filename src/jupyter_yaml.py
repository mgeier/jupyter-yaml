import json as _json
import re as _re

import nbformat as _nbformat
import notebook.services.contents.filemanager as _fm

SUFFIX = '.jupyter'

# RegEx from nbformat JSON schema:
_RE_JSON = _re.compile('^application/(.*\\+)?json$')

# TODO: somehow use JSON schema? nbformat.validator.get_validator(4, 2)

# TODO: allow completely empty lines (or with fewer spaces than necessary)?


def generate_lines(nb):
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
    return _Parser().parse(source)


class _Parser:

    def parse(self, source):
        if isinstance(source, str):
            source = source.splitlines()
        gen = self.line_consumer()
        gen.send(None)
        i = 0
        try:
            for i, line in enumerate(source, start=1):
                if line.endswith('\n'):
                    line = line[:-1]
                gen.send(line)
            i += 1
            gen.send(None)
        except StopIteration:
            assert False
            raise ParseError('Too much source text?', i + 1)
        except ParseError as e:
            if len(e.args) == 1:
                e.args += i,
            elif len(e.args) == 2:
                e.args = e.args[0], i - e.args[1]
            raise e
        except Exception as e:
            raise ParseError(type(e).__name__ + ': ' + str(e), i)
        gen.close()
        return self.nb

    def line_consumer(self):
        self.nb = _nbformat.v4.new_notebook()
        yield from self.parse_nbformat()
        yield from self.parse_nbformat_minor()
        yield from self.parse_the_rest()
        assert False, 'EOF'

    def parse_nbformat(self):
        line = yield
        nr = _check_word_plus_integer(line, 'nbformat')
        if nr != 4:
            raise ParseError('Only v4 notebooks are supported')
        self.nb.nbformat = nr

    def parse_nbformat_minor(self):
        line = yield
        self.nb.nbformat_minor = _check_word_plus_integer(
            line, 'nbformat_minor')

    def parse_the_rest(self):
        line = yield
        while True:
            # TODO: finish cell?
            if line is None:
                # TODO: finish cell?
                yield
                assert False, 'EOF'
            # TODO: finish cell?
            if _check_word(line, 'markdown'):
                cell = _nbformat.v4.new_markdown_cell()
                # TODO: attachments (since v4.1)
            elif line.startswith('code'):
                cell = _nbformat.v4.new_code_cell()
                if line not in ('code', 'code '):
                    cell.execution_count = _check_word_plus_integer(
                        line, 'code')
            elif _check_word(line, 'raw'):
                cell = _nbformat.v4.new_raw_cell()
                # TODO: attachments (since v4.1)
            elif _check_word(line, 'metadata'):
                self.nb.metadata = yield from self.parse_notebook_metadata()
                yield
                assert False, 'EOF'
            else:
                raise ParseError("Expected (unindented) cell type or "
                                 "'metadata', got {!r}".format(line))

            self.nb.cells.append(cell)
            cell.source, line = yield from self.parse_indented_lines()

            # TODO: check if line is None?

            cell_type = cell['cell_type']
            if cell_type in ('markdown', 'raw'):
                # TODO: parse attachments
                #yield from self.parse_???(line)
                pass
            elif cell_type == 'code':
                cell.outputs, line = yield from self.parse_code_outputs(line)

            if (line is not None and line.startswith('  ')
                    and _check_word('metadata', line[2:])):
                metadata, line = yield from self.parse_cell_metadata()
                cell.metadata = metadata
        assert False, 'EOF'

    def parse_code_outputs(self, line):
        outputs = []
        while True:
            current_output = None
            if line is None:
                break
            if not line.startswith('  '):
                break
            if line.startswith(' ' * 3):
                raise ParseError('Invalid indentation')

            # TODO: finish output?

            output_type = line[2:]
            if output_type.startswith('stream'):
                if len(output_type) < 7 or output_type[6] != ' ':
                    raise ParseError('Expected stream type')
                current_output = _nbformat.v4.new_output('stream')
                # NB: "name" is required!
                # TODO: check if name is valid?
                current_output.name = output_type[7:]
                text, line = yield from self.parse_indented_lines()
                current_output.text = text

            elif (_check_word('display_data', output_type) or
                    _check_word('execute_result', output_type)):
                current_output = _nbformat.v4.new_output(output_type)
                if output_type == 'execute_result':
                    assert self.nb.cells
                    assert self.nb.cells[-1].cell_type == 'code'
                    current_output.execution_count = \
                        self.nb.cells[-1].execution_count

                current_output.data, line = yield from self.parse_output_data()

                # TODO: output metadata ("  - metadata")

            # TODO: error

            elif output_type.startswith('metadata'):
                break
            else:
                raise ParseError('Expected cell output or "metadata"')
            outputs.append(current_output)

        return outputs, line

    def parse_output_data(self):
        data = {}
        line = yield
        while True:
            if line is None:
                break
            if not line.startswith('  - '):
                break
            mime_type = line[4:]
            if mime_type.strip() == 'metadata':
                break
            if mime_type != mime_type.strip():
                raise ParseError('Invalid MIME type: {!r}'.format(mime_type))
            # TODO: check for valid MIME type?
            content, line = yield from self.parse_indented_lines()
            if _RE_JSON.match(mime_type):
                data[mime_type] = _json.loads(content)
            else:
                data[mime_type] = content
        return data, line

    # TODO: move out of class
    def parse_indented_lines(self):
        lines = []
        while True:
            line = yield
            if line is None:
                break
            if line.startswith(' ' * 4):
                line = line[4:]
            elif not line.strip():
                line = ''  # Blank line
            else:
                break
            lines.append(line)
        return '\n'.join(lines), line

    # TODO: move out of class
    def parse_cell_metadata(self):
        lines = []
        while True:
            line = yield
            if line is None:
                break
            if line.startswith(' ' * 4):
                line = line[4:]
            elif not line.strip():
                line = ''  # Blank line
            else:
                break
            lines.append(line)
        if not lines:
            return {}, line
        return _parse_json(lines), line

    # TODO: move out of class
    def parse_notebook_metadata(self):
        lines = []
        while True:
            line = yield
            if line is None:
                break
            if line.startswith(' ' * 4):
                line = line[4:]
            elif not line.strip():
                line = ''
            else:
                raise ParseError(
                    'All notebook metadata lines must be indented by 4 spaces')
            lines.append(line)
        if not lines:
            return {}
        return _parse_json(lines)


def _parse_json(lines):
    try:
        metadata = _json.loads('\n'.join(lines))
    except _json.JSONDecodeError as e:
        raise ParseError(
            'JSON error in column {}: {}'.format(e.colno + 4, e.msg),
            len(lines) - e.lineno)
    return metadata


def _check_word_plus_integer(line, word):
    if line is None:
        line = ''
    m = _re.match(word + ' ([0-9]|[1-9][0-9]+)$', line)
    if not m:
        raise ParseError('Expected {!r} followed by an integer'.format(word))
    return int(m.group(1))


def _check_word(line, word):
    if line.startswith(word):
        if line != word:
            raise ParseError('No text allowed after {!r}'.format(word))
        return True
    else:
        return False


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
                    yield from _json_block('  - ' + k, v)
                else:
                    yield from _text_block('  - ' + k, v)
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


#def _read_traceback(lines):
#    traceback = []
#    while True:
#        frame, line = _read_prefixed_block(lines, ' ' * 4)
#        if frame.endswith('\n'):
#            # This is the normal case
#            frame = frame[:-1]
#        traceback.append(frame)
#        no_match, _, tail = line[1].partition('   ~')
#        if no_match:
#            break
#        if tail.strip():
#            raise ParseError('No text allowed after "~"', line[0])
#    return traceback, line


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


def _text_block(key, value):
    yield key + '\n'
    yield from _prefixed_block(' ' * 4, value)


def _json_block(key, value):
    yield key + '\n'
    yield from _prefixed_block(' ' * 4, _serialize_json(value))


def _serialize_json(data):
    # Options should be the same as in nbformat!
    # TODO: allow bytes? see BytesEncoder?
    return _json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)


def _parse_outputs_old(line, lines, cell):
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
                return deserialize(f)
            except Exception as e:
                raise _fm.web.HTTPError(400, str(e))

    def _save_notebook(self, os_path, nb):
        if not os_path.endswith(SUFFIX):
            return super()._save_notebook(os_path, nb)

        # TODO: raise proper exception on error?
        with self.atomic_writing(os_path, text=True,
                                 newline=None,  # "universal newlines"
                                 encoding='utf-8') as f:
            f.writelines(generate_lines(nb))
