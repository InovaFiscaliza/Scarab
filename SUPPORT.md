# Support

## Getting Help

If you need help using Scarab or have questions, here are the resources available to you:

### Documentation

- **Main Documentation**: Check [docs/README.md](./docs/README.md) for comprehensive documentation on configuration, features, and usage
- **Examples**: Review [data/examples/](./data/examples/) for real-world configuration examples
- **Test Cases**: The [tests/](./tests/) folder contains examples for various scenarios

### Reporting Issues

If you believe you've found a bug or issue with Scarab:

1. **Search existing issues**: Check the [Issues](https://github.com/InovaFiscaliza/Scarab/issues) to see if your problem has already been reported
2. **Provide details**: Include:
   - Your configuration file (with sensitive information removed)
   - Relevant log entries (with sensitive information removed)
   - Steps to reproduce the issue
   - Expected vs. actual behavior
3. **Open an issue**: Create a [new issue](https://github.com/InovaFiscaliza/Scarab/issues/new) with the label `bug`

### Feature Requests

Have an idea to improve Scarab? We'd love to hear it!

1. **Check existing requests**: Browse [Issues](https://github.com/InovaFiscaliza/Scarab/issues) for similar feature requests
2. **Describe your idea**: Explain:
   - What feature you're requesting
   - Why you need it
   - How it would improve your workflow
3. **Open an issue**: Create a [new issue](https://github.com/InovaFiscaliza/Scarab/issues/new) with the label `enhancement`

### Contributing

Interested in contributing to Scarab? See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on how to:

- Report bugs effectively
- Suggest enhancements
- Submit pull requests
- Set up your development environment

### Community

- **Discussions**: Use GitHub [Discussions](https://github.com/InovaFiscaliza/Scarab/discussions) for general questions and community conversation
- **Pull Requests**: Feel free to submit PRs with improvements or bug fixes

## Testing

Before running Scarab in production:

1. Review the configuration carefully
2. Test with the provided test scripts in [tests/](./tests/)
3. Use the sandbox environment to validate your setup
4. Check the generated logs for any warnings or errors

## FAQ

### Common Issues

**Q: Configuration file not found**
A: Ensure the path to your configuration file is correct and the file has `.json` extension.

**Q: Files not being processed**
A: Check that:
- Regex patterns in `metadata file regex` and `data file regex` match your filenames
- Folders are correctly configured in the configuration file
- View the service logs for detailed error messages

**Q: Data not consolidating correctly**
A: Verify:
- Column headers match across files
- Key column definitions are correct
- Multi-table PK/FK relationships (if used) are properly configured

**Q: Service won't start**
A: Check:
- Configuration file has all mandatory keys
- File paths are accessible
- Python environment is properly set up with `uv sync`

### Getting More Information

- Check application logs (configured in the `log` section)
- Review the detailed [documentation](./docs/README.md)
- Search existing [GitHub Issues](https://github.com/InovaFiscaliza/Scarab/issues)
- See [test examples](./tests/README.md) for various scenarios

## Security Issues

**Do NOT** open a public issue for security vulnerabilities. Instead, see [SECURITY.md](./SECURITY.md) for responsible disclosure procedures.

## Code of Conduct

Please note that this project is governed by a [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.
