# Github Actions: Rust Clippy

![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)

Github action to run clippy against a repository, this providers linting with the following features;

- Globbing for repositories that have multiple rust projects in them
- SSH key for projects that use cargo to pull private Git repositories
- Error and Warning outputs that highlight specific lines on PR's and commits

![alt text](gh_lint_example.png "GitHub Lint Example")

## Workflow configuration

To use this action, define it in your workflow;

```yaml
on: [push, pull_request]

jobs:
  lint:
    runs-on: self-hosted
    name: Lint package
    steps:
      - uses: actions/checkout@v2
      - uses: qernal/github-actions-rust-clippy@v1.1
```

## Action parameters

> Note: `args` is not yet implemented, `path_glob` and `git_ssh_key` are

| Parameter | Description | Required |
| ---- | ---- | ---- |
| `args` | Arguments for clippy configuration | N |
| `path_glob` | Glob for path finding (when a repository has multiple rust projects) | N |
| `git_ssh_key` | Base64 encoded SSH key used for cargo when private git repositories are specified | N |

Example;

```yaml
    steps:
      - uses: actions/checkout@v2
      - uses: qernal/github-actions-rust-clippy@v1.1
        with:
          args: "--"
          path_glob: "**/src"
          git_ssh_key: "${{ secrets.base64_ssh_key }}" # Must be base64 encoded and a valid RSA key
```

## Manual runs

You can use the container without the context of the runner, and just run the container like so;

```bash
docker run --rm -v `pwd`:/github/workspace ghcr.io/qernal/gh-actions/rust-clippy-x86_64:latest
```

Replace the `pwd` with your workspace if you're not running from the current directory
