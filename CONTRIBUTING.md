# Contributing to Scarab

First off, thanks for taking the time to contribute! It's people like you that make Scarab such an amazing tool.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [issue list](https://github.com/InovaFiscaliza/Scarab/issues) as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs if possible**
* **Include your configuration file** (with sensitive information removed)
* **Include log files** (with sensitive information removed)

### Suggesting Enhancements

Enhancement suggestions are tracked as [GitHub issues](https://github.com/InovaFiscaliza/Scarab/issues). Please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and expected behavior**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow the Python style guide (PEP 8)
* Include appropriate test cases
* Document new code with docstrings
* End all files with a newline
* Use meaningful commit messages

## Development Setup

1. Clone the repository
2. Install [UV](https://docs.astral.sh/uv/)
3. Run `uv sync` to install dependencies
4. Create a feature branch: `git checkout -b feature/your-feature`
5. Make your changes and add tests
6. Run tests from the `tests/` folder
7. Commit with clear messages: `git commit -am 'Add some feature'`
8. Push to the branch: `git push origin feature/your-feature`
9. Open a Pull Request

## Testing

Please run the appropriate test scripts from the [tests](./tests/) folder before submitting a pull request. Example tests are provided for various scenarios.

## Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Use type hints in function signatures
- Write descriptive docstrings for functions and classes
- Use meaningful variable names

## Additional Notes

### Issue and Pull Request Labels

This section lists the labels we use to help organize and categorize issues and pull requests.

* `bug` - Something isn't working
* `enhancement` - New feature or request
* `documentation` - Improvements or additions to documentation
* `good first issue` - Good for newcomers
* `help wanted` - Extra attention is needed
* `question` - Further information is requested

## Recognition

Contributors will be recognized in the project and release notes.

Thank you for contributing to Scarab!
