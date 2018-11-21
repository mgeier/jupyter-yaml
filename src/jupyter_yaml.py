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
            yield from _json_block('  ', 'metadata', cell.metadata)
        # TODO: warning/error if there are unknown attributes
    if nb.metadata:
        yield from _json_block('', 'metadata', nb.metadata)
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
    parser = _Parser()
    function = parser.parse
    for i, line in enumerate(source, start=1):
        if line.endswith('\n'):
            line = line[:-1]
        try:
            function = function(line)
        except ParseError as e:
            e.args += i,
            raise e
        except Exception as e:
            raise ParseError(type(e).__name__ + ': ' + str(e), i)
    function = function(None)
    assert function is None
    # TODO: is there more stuff left to do?
    return parse.nb


class _Parser:

    def __init__(self):
        self.nb = _nbformat.v4.new_notebook()
        self.nb.nbformat_minor = None
        self.current_source_lines = []
        self.current_output = None
        self.current_output_stream_lines = []
        self.current_output_data_lines = []
        self.current_cell_metadata = []

    def _parse_nbformat(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        if line.rstrip() != 'nbformat 4':
            raise ParseError('First line must be exactly "nbformat 4"')
        self.nb.nbformat = 4
        return self._parse_nbformat_minor

    parse = _parse_nbformat

    def _parse_nbformat_minor(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        name, _, value = line.partition(' ')
        if name != 'nbformat_minor':
            raise ParseError('Second line must start with "nbformat_minor" '
                             '(followed by a space and a number)')
        try:
            self.nb.nbformat_minor = int(value)
        except ValueError:
            raise ParseError(
                'Invalid value for "nbformat_minor": {!r}'.format(value))
        return self._parse_cell

    def _parse_cell(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        if line.startswith(' '):
            raise ParseError('Expected unindented text')
        self._finish_cell()
        if line.startswith('markdown'):
            if line[len('markdown'):].strip():
                raise ParseError('No text allowed after "markdown"')
            cell = _nbformat.v4.new_markdown_cell()
            # TODO: attachments (since v4.1)
        elif line.startswith('code'):
            cell = _nbformat.v4.new_code_cell()
            tail = line[len('code'):].strip()
            if tail:
                try:
                    cell.execution_count = int(tail)
                except ValueError:
                    raise ParseError(
                        'Invalid execution count: {!r}'.format(tail))
        elif line.startswith('raw'):
            if line[len('raw'):].strip():
                raise ParseError('No text allowed after "raw"')
            cell = _nbformat.v4.new_raw_cell()
            # TODO: attachments (since v4.1)
        elif line.startswith('metadata'):
            if line[len('metadata'):].strip():
                raise ParseError('No text allowed after "metadata"')
            return self._parse_notebook_metadata
        else:
            raise ParseError('Expected cell type or "metadata"')
        self.nb.cells.append(cell)
        return self._parse_indented_block(4, self.current_source_lines,
                                          self._parse_after_source)

    def _parse_indented_block(self, indent, target, next_function):

        def parse(line):
            if line is None:
                # TODO
                raise NotImplementedError
            if not line.startswith(' ' * indent):
                if line.startswith(' ' * (indent - 1)):
                    raise ParseError('Invalid indentation')
                return next_function(line)
            target.append(line[indent:])
            return self._parse_indented_block(indent, target, next_function)

        return parse

    def _parse_after_source(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        if not line.startswith('  '):
            return self._parse_cell(line)
        assert self.nb.cells
        cell_type = self.nb.cells[-1]['cell_type']
        if cell_type == 'markdown':
            return self._parse_markdown_data(line)
        if cell_type == 'code':
            return self._parse_outputs(line)
        # TODO: raw cells (attachments?)
        raise RuntimeError('cell data')

    def _parse_markdown_data(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        assert line.startswith('  ')
        # TODO: generalize (attachments?)

        # TODO: check for data (attachments)

        return self._parse_cell_metadata(line)

    def _parse_outputs(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        if not line.startswith('  '):
            return self._parse_cell(line)
        if line.startswith(' ' * 3):
            raise ParseError('Invalid indentation')

        self._finish_output()

        output_type = line[2:].rstrip()
        if output_type.startswith('stream'):
            if output_type[6] != ' ':
                raise ParseError('Expected "stream stdout" or "stream stderr"')
            self.current_output = _nbformat.v4.new_output('stream')
            # NB: "name" is required!
            # TODO: check if name is valid?
            self.current_output.name = output_type[7:].lstrip(' ')
            return self._parse_indented_block(
                4, self.current_output_stream_lines, self._parse_outputs)

        # TODO: if display_data, execute_result, error
        elif output_type in ('display_data', 'execute_result'):
            self.current_output = _nbformat.v4.new_output(output_type)
            if output_type == 'execute_result':
                assert self.nb.cells
                assert self.nb.cells[-1].cell_type == 'code'
                self.current_output.execution_count = \
                    self.nb.cells[-1].execution_count

            return self._parse_output_data

        elif output_type.startswith('metadata'):
            return self._parse_cell_metadata(line)
        else:
            raise ParseError('Expected cell output or "metadata"')

    def _parse_output_data(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        if not line.startswith('  '):
            return self._parse_cell(line)
        if not line.startswith('  - '):
            return self._parse_outputs(line)
        self._finish_output_data()
        mime_type = line[4:].rstrip()
        if mime_type == 'metadata':
            # TODO: parse indented, afterwards _parse_outputs
            assert False
        self.current_mime_type = mime_type
        return self._parse_indented_block(4, self.current_output_data_lines,
                                          self._parse_output_data)

    def _parse_cell_metadata(self, line):
        if line is None:
            # TODO
            raise NotImplementedError
        assert line.startswith('  ')
        line = line[2:]
        prefix, _, tail = line.partition('metadata')
        if prefix == '':
            if tail.strip():
                raise ParseError('No text allowed after "metadata"')
            return self._parse_indented_block(4, self.current_cell_metadata,
                                              self._parse_cell)
        raise ParseError('TODO: error message')

    def _parse_notebook_metadata(self, line):
        return NotImplemented

    #def finish(self):
    #    if self.nb.nbformat_minor is None:
    #        raise ParseError('The first two lines must specify "nbformat" '
    #                         'and "nbformat_minor"')
    #    self._finish_cell()
    #    # TODO: finish notebook metadata?

    #    # TODO: validate notebook?
    #    return self.nb

    def _finish_output_data(self):
        if self.current_output_data_lines:
            assert self.current_output
            assert self.current_output.output_type in ('display_data',
                                                       'execute_result')
            assert self.current_mime_type

            data = '\n'.join(self.current_output_data_lines)
            mime_type = self.current_mime_type
            if _RE_JSON.match(mime_type):
                self.current_output.data[mime_type] = _json.loads(data)
            else:
                self.current_output.data[mime_type] = data
            self.current_output_data_lines = []

        # TODO: store output metadata

    def _finish_output(self):
        if self.current_output_stream_lines:
            assert self.current_output
            assert self.current_output.output_type == 'stream'
            self.current_output.text = '\n'.join(
                self.current_output_stream_lines)
            self.current_output_stream_lines = []

        self._finish_output_data()

        if self.current_output:
            assert self.nb.cells
            self.nb.cells[-1].outputs.append(self.current_output)
            self.current_output = None

    def _finish_cell(self):
        if self.current_source_lines:
            assert self.nb.cells
            self.nb.cells[-1].source = '\n'.join(self.current_source_lines)
            self.current_source_lines = []

        self._finish_output()

        if self.current_cell_metadata:
            assert self.nb.cells
            self.nb.cells[-1].metadata = _json.loads(
                '\n'.join(self.current_cell_metadata))
            self.current_cell_metadata = []

        # TODO: finish other data


def from_nonyaml_old(source):
    """

    *source* must be either a `str` or an iterable of `str`.

    In both cases, lines have to be terminated with ``'\\n'``
    (a.k.a. "universal newlines" mode).

    """
    try:
        line = next(lines)
        while True:

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
