#!/usr/bin/env python3
"""
6G-RESCUE Edge ML Backend Setup
Newcastle University - 6G-PATH Project
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements from requirements.txt
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="6g-rescue-edge-ml-backend",
    version="1.0.0",
    author="Newcastle University",
    author_email="akumar@newcastle.ac.uk",
    description="Edge ML Operations Backend for 6G-RESCUE Project",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/newcastle-university/6g-rescue-edge-ml",
    project_urls={
        "Bug Tracker": "https://github.com/newcastle-university/6g-rescue-edge-ml/issues",
        "Documentation": "https://6g-path.eu/",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.11.0",
            "flake8>=6.1.0",
            "pre-commit>=3.5.0",
        ],
        "gpu": [
            "opencv-contrib-python>=4.8.1.78",  # GPU-accelerated OpenCV
        ],
        "production": [
            "gunicorn>=21.2.0",
            "prometheus-client>=0.19.0",  # For monitoring
        ],
    },
    entry_points={
        "console_scripts": [
            "6g-rescue-backend=main:main",
            "6g-rescue-stream=mqtt_stream_client:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml"],
    },
    keywords=[
        "6G", "edge-computing", "machine-learning", "face-recognition", 
        "rtsp", "mqtt", "jupyter", "mlops", "rescue", "disaster-management"
    ],
)