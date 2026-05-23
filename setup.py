from setuptools import setup, find_packages

setup(
    name="gdg_krakow_tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-adk",
        "google-genai",
        "google-api-python-client",
        "google-auth-oauthlib",
        "google-auth",
        "requests",
        "pillow",
        "pypdfium2",
        "python-dotenv",
    ],
)
