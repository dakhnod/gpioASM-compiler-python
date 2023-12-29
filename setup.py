import setuptools

packaged = ['compiler']

setuptools.setup(
    name='gpioasm',
    version='0.0.1',
    author='Daniel Dakhno',
    author_email='dakhnod@gmail.com',
    project_urls={
        'Source': 'https://github.com/dakhnod/gpioASM-compiler-python'
    },
    description='gpioASM compiler',
    packages=['gpioasm']
)