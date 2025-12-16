# Contributing to `django-tasks-cloud`

Thank you for your interest in contributing to **`django-tasks-cloud`**. Contributions of all kinds are welcome, including bug reports, feature requests, documentation improvements, test coverage, and code changes.

Before submitting your first contribution, please take a moment to read this document and follow the steps below to ensure your contribution can be reviewed and merged efficiently. Please take the guidelines below into consideration while making your contributions, as the maintainers of this repository have OCD.

## How to Contribute

Before following the steps mentioned below, please raise an issue. Let us know the what and why of your contribution. Once the issue is approved, you can proceed with the steps below.

We use the fork and pull request model for contributions:

1. Fork the repository on GitHub.
2. Clone your fork locally and create a new branch for your change.
3. Make your changes, commit them, and push the branch to your fork.
4. Open a pull request against the `main` branch of this repository. Most importantly, _refer to the issue you created earlier in the pull request description._ This provides context for your changes.

### Writing and Coding Conventions

Write clear and concise commit messages that describe the changes you made. Follow proper text casing where appropriate. Use Title Case for the main commit message, followed by sentence case for the detailed description.

Please use the following prefixes for commit messages based on the type of change you are making:

- "Feature" (for new features)
- "Fix" (for bug fixes)
- "Refactor" (for code changes that neither fix a bug nor add a feature)
- "Chore" (for documentation changes or other changes that do not modify source or test files)

Your commit message should be structured as follows:

```
<type>: Short Summary of the Change in Title Case

Detailed description of the change, if necessary.
```

For branch names, please use the following format:

```
<type-in-lowercase>/<short-description-in-kebab-case>
```

Follow Python conventions very strictly and adhere to PEP 8 style guidelines. Your commits will be evaluated against these standards. We heavily rely on linters and formatters. Our preferred tools are Ruff for linting and formatting, Pyright or Based Pyright for type checking, and UV for package management.

Thank you for helping improve _django-tasks-cloud_. Your contributions make this project better and more useful for everyone. For general advice on contributing guidelines, see GitHub Help on setting guidelines for contributors.
