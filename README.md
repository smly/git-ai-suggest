# git-ai-suggest

A helper tool that uses the Gemini CLI to suggest commit messages and pull request titles/bodies.

## Installation

```bash
uv tool install .
```

## Suggest Commit Message

```bash
# Suggest commit message for staged changes
$ g m
On branch feat/benchmark-agari
Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
        modified:   ../BENCHMARK.md
        new file:   ../DEVEL.md
        new file:   bench_agari.py
        new file:   pyproject.toml
        new file:   uv.lock

Choose commit message:
[1] feat: Implement initial benchmark script
[2] chore: Add project configuration files
[3] docs: Update benchmark documentation
[4] Cancel
> 1

Committed!
```

## Suggest Pull Request Title

```bash
# Suggest pull request title and body for the current branch
$ g p

Choose pull request title and body:
[1] feat: Add benchmark script and docs

This PR introduces a new benchmark script for Agari calculation and updates the documentation.

[2] chore: Initial project setup

Added pyproject.toml and other config files.

[3] Cancel

> 1

Created pull request!
```

## Options

- `--model <MODEL_NAME>`: Specify the Gemini model to use (default: `gemini-2.5-flash`).

## TODO

- [ ] Find commitlint config and use it to validate suggested commit messages
