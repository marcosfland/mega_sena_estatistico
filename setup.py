from setuptools import setup, find_packages

setup(
    name="mega_sena_estatistico",
    version="1.4.0",
    description="Ferramenta estatística para análise da Mega-Sena com interface gráfica e CLI.",
    author="marcosfland",
    packages=find_packages(),
    install_requires=[
        "requests",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "flask",
        "pillow",
        "pytest",
        "setuptools"
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'mega-sena-cli=cli:main',
            'mega-sena-gui=gui:main'
        ]
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
