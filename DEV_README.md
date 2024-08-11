## Getting Started

Install the `requirements_dev.txt` dependencies to set up a full dev environment.

## Building the docs

From main lt-maker directory:
`./docs/make.bat html`
to build html documentation
It will appear in _build/html

## Useful commands

To launch the editor, run `python run_editor.py`.

To run the tests, `./utilities/build_tools/run_tests.sh`, which itself is a wrapper around `python -m unittest discover -s app/tests -p 'test*.py'` - the real test-running command.

To type check, run `mypy app/`, which will run the `mypy` type checker on the entire project.