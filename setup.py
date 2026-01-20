from setuptools import setup, find_packages

setup(
    name="mca-pricing-toolkit",
    version="1.0.0",
    author="Silv MT Holdings",
    description="MCA pricing toolkit - Factor rate recommendations, advance calculations, term suggestions, and deal tier classification",
    url="https://github.com/silv-mt-holdings/mca-pricing-toolkit",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
    install_requires=[
        "mca-scoring-toolkit @ git+https://github.com/silv-mt-holdings/mca-scoring-toolkit.git",
    ],
    extras_require={"dev": ["pytest>=7.0.0"]},
    include_package_data=True,
    package_data={"": ["data/*.json"]},
)
