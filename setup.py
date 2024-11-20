from setuptools import setup, find_packages

setup(
    name='SimpleWorkTime',
    version='0.2.0',
    packages=find_packages(),
    description='A simple command-line work time tracker',
    author='John Vouvakis Manousakis',
    author_email='ioannis_vm@berkeley.edu',
    entry_points={
        'console_scripts': [
            'simpleworktime=src.main:main'
        ]
    },
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: MIT License',
        'Topic :: Utilities'
    ]
)
