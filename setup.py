from setuptools import setup


setup(
    name='derpcache',
    version='0.0.1',
    description='Simple pickle-based caching utility.',
    author='Ben Johnson',
    author_email='bkitej@gmail.com',
    install_requires=['pickle5'],
    extras_require={
        'dev': ['commitizen'],
        'linting': ['black', 'flake8'],
        'test': ['faker', 'pytest', 'pytest-freezegun'],
    },
)
