from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='django_denormalized',
    version='0.5.0',
    packages=['denormalized'],
    url='https://github.com/just-work/django-denormalized',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='Beer License',
    author='Sergey Tikhonov',
    author_email='zimbler@gmail.com',
    description='Utils for maintaining denormalized '
                'aggregates for Django models',
    install_requires=['Django']
)
