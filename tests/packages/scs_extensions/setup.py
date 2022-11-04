from setuptools import setup, find_packages

setup(
    name="scs-extensions",
    version="1.0.0",
    packages=find_packages(),
    description=(
        "Package containing dummy scs extensions used in tests. Note that "
        "this package cannot be used stand-alone"
    ),
)
