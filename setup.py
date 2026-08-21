from setuptools import find_packages, setup

setup(
    name="gdg_krakow_tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-adk",
        "a2a-sdk",
        "google-genai",
        "google-api-python-client",
        "google-auth-oauthlib",
        "google-auth",
        "requests",
        "pillow",
        "pypdfium2",
        "python-dotenv",
        "openpyxl",
        "python-docx",
        "uvicorn",
        "sse-starlette",
    ],
)
