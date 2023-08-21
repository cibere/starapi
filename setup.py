import re

from setuptools import setup

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

version = ""
with open("starapi/__init__.py") as f:
    version = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE
    ).group(  # type: ignore
        1
    )

if not version:
    raise RuntimeError("version is not set")

if version.endswith(("a", "b", "rc")):
    # append version identifier based on commit count
    try:
        import subprocess

        p = subprocess.Popen(
            ["git", "rev-list", "--count", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += out.decode("utf-8").strip()
        p = subprocess.Popen(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if out:
            version += "+g" + out.decode("utf-8").strip()
    except Exception:
        pass

readme = ""
with open("README.md") as f:
    readme = f.read()

extras_require = {
    "all": {
        "uvicorn[standard]",
        "python-multipart",
        "msgspec",
        "tomli_w",
        "pyyaml",
    },
    "standard": {
        "uvicorn[standard]",
        "msgspec",
    },
    "payload": {
        "msgspec",
        "pyyaml",
        "tomli_w",
    },
}

packages = [
    "starapi",
]

setup(
    name="starapi",
    author="cibere",
    url="https://github.com/cibere/starapi",
    project_urls={
        "Issue tracker": "https://github.com/cibere/starapi/issues",
    },
    version=version,
    packages=packages,
    license="MIT",
    description="An ASGI framework",
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    python_requires=">=3.11.0",
)
