from setuptools import setup, find_packages
import os
import time


# create files that will be excluded from the repository from list of tuples
# first tuple element is the filename with directory, second is the file content
RESET_PRIVATE = os.getenv("F9_RESET_PRIVATE", "0") == "1"

credentials_template = '''\n# update the below with desired credentials (semi-secure demo storage)\n# Existing file preserved unless F9_RESET_PRIVATE=1 is set in environment.\n# To force regeneration: F9_RESET_PRIVATE=1 pip install -e .\n\nACCOUNTS = {\n    'default_account': {\n        'username': 'apiUserUsername',\n        'password': 'apiUserPassword'\n    },\n    # 'default_test_account': {\n    #     'username': 'yourTestUser',\n    #     'password': 'yourTestPass'\n    # },\n}\n'''

bootstrap_files = [
    ("private/credentials.py", credentials_template),
    ("private/__init__.py", ""),
    ("private/users_to_update.csv", "")
]

for path, content in bootstrap_files:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith("credentials.py"):
        if os.path.exists(path) and not RESET_PRIVATE:
            # Preserve existing credentials
            continue
        if os.path.exists(path) and RESET_PRIVATE:
            ts = time.strftime('%Y%m%d-%H%M%S')
            backup_path = f"{path}.backup.{ts}"
            try:
                with open(path, 'r') as rf:
                    original = rf.read()
                with open(backup_path, 'w') as bf:
                    bf.write(original)
            except OSError:
                pass  # best-effort backup
        with open(path, 'w') as wf:
            wf.write(content)
    else:
        # create ancillary file only if it does not exist to avoid clobbering user data
        if not os.path.exists(path):
            with open(path, 'w') as wf:
                wf.write(content)

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='five9',
    version='1.1.0',
    packages=find_packages(),
    description='A Five9 Configuration Webserivce API wrapper',
    long_description=open('README.md').read(),
    install_requires=requirements,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.12',
    ],
)

