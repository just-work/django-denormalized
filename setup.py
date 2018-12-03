from setuptools import setup

setup(
    name='django_denormalized',
    version='0.1.0',
    packages=['denormalized'],
    url='https://github.com/tumb1er/django-denormalized',
    license='Beer License',
    author='Sergey Tikhonov',
    author_email='zimbler@gmail.com',
    description='Utils for maintaining denormalized '
                'aggregates for Django models',
    install_requires=['Django']
)
