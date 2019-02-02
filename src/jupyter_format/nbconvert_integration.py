"""
"""
from nbconvert.exporters.exporter import Exporter as _Exporter
from nbconvert.exporters.notebook import NotebookExporter
import traitlets as _traitlets

import jupyter_format as _jf


class Exporter(_Exporter):
    """Convert Jupyter notebooks to ``.jupyter`` format."""

    @_traitlets.default('file_extension')
    def _file_extension_default(self):
        return _jf.SUFFIX

    def from_notebook_node(self, nb, resources=None, **kwargs):
        if nb.nbformat < 4:
            nb = nbformat.convert(nb, 4)
        elif nb.format > 4:
            raise RuntimeError("Jupyter notebook format > 4 is not supported")
        nb, resources = super().from_notebook_node(nb, resources, **kwargs)

        #output_dir = resources['output_files_dir']
        #util.ensure_new_directory(output_dir)

        #dumper = _make_dumper(output_dir)

        #out = {}
        #out['cells'] = []
        #for cell in nb.cells:
        #    out_cell = _Cell(cell)
        #    if hasattr(cell, 'outputs'):
        #        out_cell['outputs'] = [
        #            _Output(x) for x in cell.outputs]
        #    out['cells'].append(out_cell)

        #out['nbformat'] = nb.nbformat
        #out['nbformat_minor'] = nb.nbformat_minor
        #out['metadata'] = dict(nb.metadata)

        #return (
        #    yaml.dump(out, Dumper=dumper, default_flow_style=False),
        #    resources)

        return _jf.serialize(nb), resources


class Importer(_Exporter):
    """Convert ``.jupyter`` files to internal data structure."""

    @default('file_extension')
    def _file_extension_default(self):
        return '.ipynb'

    def from_filename(self, filename, resources=None, **kwargs):
        root_dir = os.path.dirname(filename)

        with open(filename, 'r', encoding='utf-8', newline=None) as f:
            nb = _jf.deserialize(f)

        #for cell in tree['cells']:
        #    if 'metadata' not in cell:
        #        cell['metadata'] = {}
        #    if 'outputs' in cell:
        #        for output in cell['outputs']:
        #            if (output['output_type'] != 'stream' and
        #                    'metadata' not in output):
        #                output['metadata'] = {}
        #            if 'data' in output:
        #                for key, val in list(output['data'].items()):
        #                    output['data'][key] = output_types.load_output(
        #                        root_dir, key, val)
        #    elif cell['cell_type'] == 'code':
        #        cell['outputs'] = []

        #output_file = io.StringIO()
        #json.dump(tree, output_file)
        #output_file.seek(0)

        ## Send the above ad-hoc JSON through nbconvert's built-in notebook
        ## exporter so all of the formatting details are the same as for
        ## standard notebooks.
        #notebook_exporter = NotebookExporter()
        #return notebook_exporter.from_file(output_file, resources=resources, **kwargs)

        return nb
