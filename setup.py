from setuptools import find_packages, setup

setup(
    name="roon-full-art-display",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["requests", "pillow", "roonapi", "configparser", "numpy"],
    extras_require={"dev": ["pytest", "pytest-mock", "pytest-cov"]},
    python_requires=">=3.8",
)
