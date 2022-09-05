from setuptools import setup


setup(
    name='derpcache',
    version='0.0.1',
    description='Simple pickle-based caching utility.',
    author='Ben Johnson',
    author_email='bkitej@gmail.com',
    install_requires=[
        'pickle5==0.0.11',
    ],
    extras_require={
        'dev': [
            'commitizen==2.32.2',
            'pre-commit==2.20.0',
        ],
        'lint': [
            'black==22.8.0',
            'flake8<4',  # flakehell incompatible with >=4
            'flakehell==0.9.0',
            'mypy==0.971',
            'types-setuptools==65.3.0',
        ],
        'test': [
            'faker==14.2.0',
            'pytest==7.1.2',
            'pytest-freezegun==0.4.2',
        ],
    },
    zip_safe=False,  # for mypy to detect typing stubs
)
