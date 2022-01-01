from setuptools import setup


setup(
    name='skylark',
    version='0.1',
    packages=["skylark"],
    python_requires=">=3.8",
    install_requires=[
        "awscrt",
        "boto3",
        "click",
        "cvxopt",
        "cvxpy",
        "flask",
        "google-api-python-client",
        "google-cloud-compute",
        "graphviz",
        "loguru",
        "matplotlib",
        "numpy",
        "pandas",
        "paramiko",
        "questionary",
        "ray",
        "setproctitle",
        "tqdm",
        "werkzeug",
    ],
    extras_require={"test": ["black", "pytest", "ipython", "jupyter_console"]}
)