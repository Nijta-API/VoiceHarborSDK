from setuptools import setup, find_packages

setup(
    name="voice-harbor-client",
    version="0.1.0",
    author="Seyed Ahmad Hosseini",
    author_email="arash@nijta.com",
    description="A Python client for the Voice Harbor service.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Nijta-API/voice-harbor-client/python",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pyyaml",
        "tqdm",
    ],
    entry_points={
        'console_scripts': [
            'voice-harbor-client=voice_harbor_client.python.client:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
