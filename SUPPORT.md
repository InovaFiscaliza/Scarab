# Support

## Getting Help

If you need help using Scarab or have questions, here are the resources available to you:

### Documentation

- **Main Documentation**: Check [README.md](./README.md) for architecture, configuration, and usage
- **Architecture Contracts**: Review [docs/architecture/CONTRACTS.md](./docs/architecture/CONTRACTS.md) for module and database contracts
- **Test Suite**: Run `uv run pytest` to validate the active implementation

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
2. Run the automated suite with `uv run pytest`
3. Install a test instance with `deploy/scarab-deploy.sh`
4. Run `scarab-deploy test --instance scarab-test`
5. Check the generated logs for any warnings or errors

## FAQ

### Common Issues

**Q: Configuration file not found**
A: Ensure the path to your configuration file is correct and the file has `.json` extension.

**Q: Files not being processed**
A: Check that:
- Input repositories are correctly configured
- The JSON contains a supported `operacao` value
- View the service logs for detailed error messages

**Q: Data not consolidating correctly**
A: Verify:
- The JSON payload is valid and contains the configured business key when one is required
- The PostgreSQL function is installed and reachable
- The database logs contain no rejected operation

**Q: Service won't start**
A: Check:
- Configuration file has all mandatory keys
- File paths are accessible
- Python environment is properly set up with `uv sync`

### Getting More Information

- Check application logs (configured in the `log` section)
- Review the [README](./README.md) and [architecture contracts](./docs/architecture/CONTRACTS.md)
- Search existing [GitHub Issues](https://github.com/InovaFiscaliza/Scarab/issues)
- Run `uv run pytest` for the current regression suite

## Security Issues

**Do NOT** open a public issue for security vulnerabilities. Instead, see [SECURITY.md](./SECURITY.md) for responsible disclosure procedures.

## Code of Conduct

Please note that this project is governed by a [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.
