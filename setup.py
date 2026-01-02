from setuptools import setup, find_packages

setup(
    name="financeiro-familiar",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.30.0,<1.31",
        "psycopg2-binary>=2.9.9,<2.10",
        "python-dotenv>=1.0.0,<1.1",
        "pandas>=2.1.4,<2.2",
        "SQLAlchemy>=2.0.25,<2.1",
    ],
    python_requires=">=3.11",
)