# Github Actions: Rust Clippy

![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)

Github action to run clippy against a repository

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
      - uses: qernal/github-actions-rust-clippy@v1
```

## Action parameters

> Note: These are yet to be implemented

| Parameter | Description | Required |
| ---- | ---- | ---- |
| `args` | Arguments for clippy configuration | N |
| `path_glob` | Glob for path finding (when a repository has multiple rust projects) | N |

Example;

```yaml
    steps:
      - uses: actions/checkout@v2
      - uses: qernal/github-actions-rust-clippy@v1
        with:
          args: "--"
          path_glob: "**/src"
```

## Manual runs

You can use the container without the context of the runner, and just run the container like so;

```bash
docker run --rm -v `pwd`:/github/workspace ghcr.io/qernal/gh-actions/rust-clippy-x86_64:latest
```

Replace the `pwd` with your workspace if you're not running from the current directory