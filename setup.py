from setuptools import setup, find_packages

setup(
    name="financeiro-familiar",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.30.0",
        "psycopg2-binary>=2.9.9",
        "python-dotenv>=1.0.0",
        "pandas>=2.2.1",
        "SQLAlchemy>=2.0.25",
    ],
    python_requires=">=3.11",
)