"""
Setup script for Exivity Management CLI
"""

from setuptools import setup, find_packages

setup(
    name="exivity-cli",
    version="1.0.0",
    description="Exivity Management CLI - A comprehensive command-line interface for managing Exivity instances",
    author="Exivity",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "questionary>=1.10.0",
        "urllib3>=1.26.0",
        "PyYAML>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "exivity-cli=exivity_cli.main:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
