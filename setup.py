from setuptools import setup
import os

setup(
    name='studentvue',
    packages=['studentvue'],
    version='2.0.1',
    description='Unofficial Python API Client for StudentVue Portals',
    author='Kai Chang',
    url='https://github.com/StudentVue-Community/StudentVue',
    license='MIT',
    long_description_content_type='text/markdown',
    long_description=open(os.path.join(os.path.abspath(
        os.path.dirname(__file__)), 'README.md')).read(),
    install_requires=[open(os.path.join(os.path.abspath(
        os.path.dirname(__file__)), 'requirements.txt')).read().split('\n')[:-1]]
)
