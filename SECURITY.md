# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Scarab, please **do not** open a public GitHub issue. Instead, please report it responsibly by:

1. **Email**: Contact the maintainers directly (check the repository for contact information)
2. **GitHub Security Advisory**: Use GitHub's private vulnerability reporting feature if available for this repository

When reporting a vulnerability, please include:

* Type of vulnerability
* Location of the affected code (file, line number, or function)
* Description of the vulnerability
* Potential impact of the vulnerability
* Suggested fix (if you have one)

We will:

* Acknowledge receipt of your report
* Investigate the vulnerability
* Work on a fix
* Coordinate a timeline for releasing the patch
* Credit you in the security bulletin (if you wish to be credited)

## Security Considerations

When using Scarab, please be aware of the following:

### Configuration Files

- **Sensitive Data**: Configuration files should not contain sensitive information like passwords or API keys
- **File Permissions**: Protect your configuration files and sandboxes from unauthorized access
- **Backup**: Keep backups of important configuration and data files

### File Operations

- **Path Validation**: Ensure input/output folder paths are properly configured
- **Regex Patterns**: Test regex patterns thoroughly to avoid unexpected file matching
- **File Permissions**: Ensure proper file permissions for read/write operations

### Metadata Handling

- **Data Validation**: Always validate input metadata files before processing
- **Column Names**: Be cautious with special characters that may be stripped by the character scope regex
- **PK/FK Relationships**: Test multi-table relationships thoroughly before production use

### Logging

- **Log Security**: Log files may contain sensitive metadata - protect them accordingly
- **Log Rotation**: Implement log rotation to manage file sizes and archive old logs securely

## Best Practices

1. **Regular Updates**: Keep Scarab and its dependencies up to date
2. **Testing**: Thoroughly test configurations in a sandbox environment before production
3. **Monitoring**: Monitor application logs for errors and unusual patterns
4. **Access Control**: Restrict access to Scarab configuration and data folders
5. **Backups**: Maintain regular backups of your metadata and configuration
6. **Documentation**: Document your configuration and setup for security audits

## Supported Versions

Please check the [releases](https://github.com/InovaFiscaliza/Scarab/releases) page for information about supported versions and security updates.
