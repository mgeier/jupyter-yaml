import nbformat as _nbformat
from notebook.services.contents.filemanager import FileContentsManager as _CM

SUFFIX = '.jupyter'


class FileContentsManager(_CM):

    def get(self, path, content=True, type=None, format=None):
        if type is None and path.endswith(SUFFIX):
            type = 'notebook'
        return _CM.get(self, path, content, type, format)

    def _read_notebook(self, os_path, as_version=4):
        # TODO: catch exceptions, raise HTTPError?
        with self.open(os_path, 'r', encoding='utf-8') as f:
            return _nbformat.read(f, as_version=as_version)

    def _save_notebook(self, os_path, nb):
        # TODO: raise proper exception on error?
        with self.atomic_writing(os_path, encoding='utf-8') as f:
            _nbformat.write(nb, f, version=_nbformat.NO_CONVERT)
