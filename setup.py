from setuptools import setup

# "import" __version__
__version__ = 'unknown'
for line in open('src/jupyter_format/__init__.py'):
    if line.startswith('__version__'):
        exec(line)
        break

setup(
    name='jupyter_format',
    version=__version__,
    package_dir={'': 'src'},
    packages=['jupyter_format'],
    install_requires=['nbformat'],
    python_requires='>=3.4',
    author='Matthias Geier',
    author_email='Matthias.Geier@gmail.com',
    description='An Experimental New Storage Format For Jupyter Notebooks',
    long_description=open('README.rst').read(),
    license='MIT',
    keywords=''.split(),
    url='',
    platforms='any',
    classifiers=[
        'Framework :: Jupyter',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
    zip_safe=True,
    entry_points={
        'nbconvert.exporters': [
            'jupyter = jupyter_format.nbconvert_integration:Exporter',
            'jupyter_notebook = jupyter_format.nbconvert_integration:Importer',
        ],
    },
)
