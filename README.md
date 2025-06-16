# PROJECT_NAME

Main part is client. Client reads sensors data and sends it to OPC UA server. There is config.json file to specify server URL and other parameters like node ids.

Server is for test purposes. It is just echo server.

# Client requirements

Windows-only application.

Supports x86 and x86_64.

Pre-requirements:
* Python 3.7 or later,
* .NET Framework 4.5 or Mono.

Administrator access is required to use tcp port.

# Server requirements

Cross-platform application.

Pre-requirements:
* Python 3.7 or later.

On Windows administrator access is required to listen tcp port.

# First run

Steps for first run.

1) Download project from git.

2) Open terminal in the project dir.

3) Create virtual environment.
```
python -m venv venv
```

4) Activate virtual environment.
```
. venv/bin/activate
```

5) Update pip and setuptools.
```
python -m pip install -U pip setuptools
```

6. Install required python libraries.
```
pip install -r requirements.txt
```

7. Run server.
```
python server.py
```

8. Open second terminal, activate environment and run client.
```
python client.py
```

# Second run

1. In the porject dir activate the environment.
```
. venv/bin/activate
```

2. Run client or server.
```
python client.py
```
