"""
"""
import json as _json

import nbconvert.exporters as _exp
import nbformat as _nbformat
import traitlets as _traitlets
import jupyter_format as _jf


class JupyterImportMixin:
    """Allow ``*.jupyter`` files as input to exporters."""

    def from_filename(self, filename, resources=None, **kw):
        if filename.endswith(_jf.SUFFIX):
            if resources is None:
                resources = _exp.ResourcesDict()
            resources.setdefault('output_extension', self.file_extension)
            kw.setdefault('jupyter_format', True)
        return super().from_filename(filename, resources, **kw)

    def from_file(self, file, resources=None, jupyter_format=None, **kw):
        if jupyter_format:
            return self.from_notebook_node(
                _jf.deserialize(file), resources=resources, **kw)
        return super().from_file(file, resources=resources, **kw)


class JupyterExporter(JupyterImportMixin, _exp.Exporter):
    """Convert Jupyter notebooks to ``.jupyter`` format."""

    @_traitlets.default('file_extension')
    def _file_extension_default(self):
        return _jf.SUFFIX

    def from_notebook_node(self, nb, resources=None, **kw):
        if nb.nbformat != 4:
            nb = _nbformat.convert(nb, to_version=4)
        nb, resources = super().from_notebook_node(nb, resources, **kw)
        return _jf.serialize(nb), resources


class TemplateExporter(JupyterImportMixin, _exp.TemplateExporter):
    pass


class HTMLExporter(JupyterImportMixin, _exp.HTMLExporter):
    pass


class SlidesExporter(JupyterImportMixin, _exp.SlidesExporter):
    pass


class LatexExporter(JupyterImportMixin, _exp.LatexExporter):
    pass


class PDFExporter(JupyterImportMixin, _exp.PDFExporter):
    pass


class MarkdownExporter(JupyterImportMixin, _exp.MarkdownExporter):
    pass


class PythonExporter(JupyterImportMixin, _exp.PythonExporter):
    pass


class RSTExporter(JupyterImportMixin, _exp.RSTExporter):
    pass


class NotebookExporter(JupyterImportMixin, _exp.NotebookExporter):
    pass


class ASCIIDocExporter(JupyterImportMixin, _exp.ASCIIDocExporter):
    pass


class ScriptExporter(JupyterImportMixin, _exp.ScriptExporter):
    pass
