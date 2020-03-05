from setuptools import setup, find_packages


data_files = [
    ('/etc/librescripts', ['install/conf/search_folders.json']),
    ('/etc/cron.d',       ['install/cron/update_metadata']),
]


setup(
    name="LibreTimeScripts",
    version="0.1",
    author="@kmahelona",
    description="A collection of scripts to help with automated ingesting of media to LibreTime",
    packages=['radio_database_sync'],
    install_requires=[
        "mutagen",
        "python-magic",

    ],
    entry_points={
        "console_scripts": [
            "radio-db-sync = radio_database_sync.update_metadata:main"
        ]
    }

)
