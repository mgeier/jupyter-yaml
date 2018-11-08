from jupyter_yaml import to_yaml
import nbformat
import pytest


@pytest.fixture
def nb():
    return nbformat.v4.new_notebook()


def test_minimal_notebook(nb):
    nb.nbformat_minor = 1
    assert to_yaml(nb) == 'nbformat: 4\nnbformat_minor: 1\ncells:\nmetadata:\n'


def test_only_version_4_is_allowed(nb):
    nb.nbformat = 5
    with pytest.raises(RuntimeError) as excinfo:
        to_yaml(nb)
    assert 'version 4' in str(excinfo.value)


def test_unknown_cell_type(nb):
    cell = nbformat.v4.new_raw_cell()
    cell.cell_type = 'nonsense'
    nb.cells.append(cell)
    with pytest.raises(RuntimeError) as excinfo:
        to_yaml(nb)
    assert "'nonsense'" in str(excinfo.value)
