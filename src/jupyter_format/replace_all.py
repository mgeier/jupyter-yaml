#!/usr/bin/env python3
"""Script to replace .ipynb with .jupyter files.

Usage to apply this to the whole history of a Git branch:

    git filter-branch --tree-filter "python3 -m jupyter_format.replace_all --recursive --yes"

"""
from pathlib import Path
import sys

from jupyter_format.exporters import JupyterExporter
from nbconvert.writers import FilesWriter


def convert_to_jupyter(path):
    exporter = JupyterExporter()
    nb, resources = exporter.from_filename(str(path))
    writer = FilesWriter()
    writer.write(nb, resources, notebook_name=path.with_suffix('').name)


def replace_all_recursive(start_dir):
    for path in Path(start_dir).rglob('*.ipynb'):
        convert_to_jupyter(path)
        path.unlink()


if __name__ == '__main__':
    if set(sys.argv[1:]) != {'--recursive', '--yes'}:
        sys.exit('This replaces all *.ipynb files recursively! '
                 'Use --recursive --yes to consent.')
    replace_all_recursive('.')
