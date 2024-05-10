from setuptools import setup

setup(
    name='ask_obsidian',
    version='0.0.1',
    entry_points={
        'console_scripts': [
            'ask_obsidian=ask_obsidian:main'
        ]
    }
)