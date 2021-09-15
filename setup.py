from setuptools import setup


setup(
    name='sanic-redis',
    version='0.3.0',
    description='Adds redis support to sanic .',
    long_description='sanic-redis is a sanic framework extension which adds support for the redis.',
    url='https://github.com/strahe/sanic-redis',
    author='octal',
    author_email="octal@posteo.net",
    license='MIT',
    packages=['sanic_redis'],
    install_requires=('sanic', 'aioredis'),
    zip_safe=False,
    keywords=['sanic', 'redis', 'aioredis'],
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP :: Session',
    ],
)
