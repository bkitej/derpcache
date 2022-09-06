from setuptools import setup


setup(
    name='derpcache',
    version='0.0.1',
    description='Simple pickle-based caching utility.',
    long_description=open('README.md', 'r').read(),
    long_description_content_type='text/markdown',
    author='Ben Johnson',
    author_email='bkitej@gmail.com',
    install_requires=[
        'pickle5',
    ],
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
