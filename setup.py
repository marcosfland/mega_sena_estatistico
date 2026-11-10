"""Instalação opcional como pacote: ``pip install -e .`` cria o comando ``loterias``."""

from setuptools import find_packages, setup

setup(
    name="loterias-estatistico",
    version="2.0.0",
    description="Estatística, geração de jogos e bolões para as loterias da Caixa (GUI e CLI).",
    author="marcosfland",
    packages=find_packages(include=["loterias", "loterias.*"]),
    install_requires=["customtkinter>=5.2", "matplotlib>=3.7", "requests>=2.31", "pillow>=10.0"],
    python_requires=">=3.10",
    entry_points={"console_scripts": ["loterias=loterias.cli:main"],
                  "gui_scripts": ["loterias-gui=loterias.gui.app:launch"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
