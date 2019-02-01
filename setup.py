from setuptools import setup

setup(
    name='jupyter_format',
    version='0.0.0',
    package_dir={'': 'src'},
    py_modules=['jupyter_format'],
    install_requires=[
        'nbformat',
    ],
    python_requires='>=3.5',
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
)
