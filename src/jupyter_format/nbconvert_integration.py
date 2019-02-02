"""
"""
import json as _json

from nbconvert.exporters.exporter import Exporter as _Exporter
from nbconvert.exporters.notebook import NotebookExporter as _NotebookExporter
import nbformat as _nbformat
import traitlets as _traitlets
import jupyter_format as _jf


class Exporter(_Exporter):
    """Convert Jupyter notebooks to ``.jupyter`` format."""

    @_traitlets.default('file_extension')
    def _file_extension_default(self):
        return _jf.SUFFIX

    def from_notebook_node(self, nb, resources=None, **kw):
        if nb.nbformat != 4:
            nb = _nbformat.convert(nb, to_version=4)
        nb, resources = super().from_notebook_node(nb, resources, **kw)
        return _jf.serialize(nb), resources


class Importer(_NotebookExporter):
    """Convert ``.jupyter`` files to internal data structure."""

    def from_filename(self, filename, resources=None, **kw):
        if filename.endswith(_jf.SUFFIX):
            if resources is not None and 'output_extension' not in resources:
                resources['output_extension'] = self.file_extension
            kw['jupyter_format'] = True
        return super().from_filename(filename, resources, **kw)

    def from_file(self, file, resources=None, jupyter_format=None, **kw):
        if jupyter_format:
            return _json.dumps(_jf.deserialize(file)), resources
        return super().from_file(file, resources=resources, **kw)
