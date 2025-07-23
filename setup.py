#!/usr/bin/env python3
"""
Setup configuration for ugly_midi package.
"""

from setuptools import setup, find_packages
import os


# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "A bidirectional converter between VexFlow-style JSON music notation and MIDI files."


# Read requirements
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            # Filter out comments and empty lines
            requirements = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    requirements.append(line)
            return requirements
    return ['pretty_midi>=0.2.8', 'numpy>=1.19.0']


setup(
    name="ugly_midi",
    version="1.0.0",
    author="Your Name",  # Replace with your name
    author_email="your.email@example.com",  # Replace with your email
    description=
    "A bidirectional converter between VexFlow-style JSON music notation and MIDI files",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url=
    "https://github.com/yourusername/ugly_midi",  # Replace with your repo URL
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio :: MIDI",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=read_requirements(),
    extras_require={
        'web': ['flask>=2.0.0', 'gunicorn>=20.0.0'],
        'dev': ['pytest>=6.0.0', 'pytest-cov>=2.10.0'],
        'all': [
            'flask>=2.0.0', 'gunicorn>=20.0.0', 'pytest>=6.0.0',
            'pytest-cov>=2.10.0'
        ]
    },
    entry_points={
        'console_scripts': [
            'ugly_midi=ugly_midi.cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        'ugly_midi': ['*.json', '*.md'],
    },
    keywords="midi music vexflow json converter audio",
    project_urls={
        "Bug Reports":
        "https://github.com/yourusername/ugly_midi/issues",
        "Source":
        "https://github.com/yourusername/ugly_midi",
        "Documentation":
        "https://github.com/yourusername/ugly_midi/blob/main/README.md",
    },
)
