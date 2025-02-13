# Install

This folder includes the necessary files to install the application in a Windows environment.

## Installation

To install the application, follow these steps:

1. Download the latest release from the [releases page](

## Creating new tests

Edit the content of the sandbox folder to create the desired structure, making modifications in the config.json file if necessary.

Run the following command to create the corresponding TGZ file:

```cmd
tar -czvf TEST_NAME.tgz sandbox
```

Where `TEST_NAME` is the name of the test to be used in the batch file.

Create the new test modifying the `TEST_NAME.bat` file, using the TEST_NAME where required.
