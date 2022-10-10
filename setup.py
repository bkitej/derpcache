from setuptools import find_packages
from setuptools import setup


with open('README.md', 'r') as f:
    long_description = f.read()


setup(
    name='derpcache',
    version='0.1.0',
    description='A simple pickle-based caching utility.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='GPL-3',
    author='Ben Johnson',
    author_email='bkitej@gmail.com',
    packages=find_packages(),
    install_requires=[],  # Nothing!
    extras_require={
        'dev': [
            'commitizen',
            'pre-commit',
        ],
        'lint': [
            'black',
            'flakeheaven',
            'mypy',
            'types-setuptools',
        ],
        'test': [
            'faker',
            'pytest',
            'pytest-freezegun',
        ],
    },
    zip_safe=False,  # for mypy to detect typing stubs
)
