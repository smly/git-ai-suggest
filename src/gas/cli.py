import argparse
import subprocess
import sys
import os
import importlib.resources


def run_git_command(args):
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        sys.exit(1)


def run_gemini(prompt, content, args, model="gemini-2.5-flash"):
    full_prompt = f"{prompt}\n\n{content}"
    try:
        # Use subprocess to call gemini CLI
        # gemini "prompt"
        if args.verbose:
            print(f"Running gemini with model {model}...")

        # Use subprocess to call gemini CLI
        # gemini --model model
        # Input is passed via stdin
        cmd = ["gemini", "--model", model]
        if args.verbose:
            print(f"Command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, input=full_prompt, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if e.stderr and "exhausted your daily quota" in e.stderr:
            print(
                "Error: Gemini API daily quota exhausted. Please try again later.",
                file=sys.stderr,
            )
        else:
            print(f"Error running gemini: {e}", file=sys.stderr)
            if e.stderr:
                print(f"Gemini stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            "Error: 'gemini' CLI not found. Please ensure it is installed and in your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_template_content(filename):
    try:
        # Assuming struct src/gas/templates/filename
        # For Python 3.9+ imports
        return importlib.resources.files("gas.templates").joinpath(filename).read_text()
    except Exception as e:
        print(f"Error reading template {filename}: {e}", file=sys.stderr)
        sys.exit(1)


def is_excluded_file(filename):
    excluded_exts = {
        ".lock",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".zip",
        ".tar.gz",
        ".tgz",
        ".exe",
        ".bin",
        ".pyc",
    }
    excluded_files = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Cargo.lock",
        "uv.lock",
    }
    if filename in excluded_files:
        return True

    _, ext = os.path.splitext(filename)
    return ext.lower() in excluded_exts


def get_file_diff(filename, staged=True, target_branch=None, max_lines=200):
    cmd = ["diff"]
    if staged:
        cmd.append("--staged")
    elif target_branch:
        cmd.append(f"{target_branch}...HEAD")

    cmd.append("--")
    cmd.append(filename)

    diff_content = run_git_command(cmd)

    if not diff_content:
        return ""

    lines = diff_content.splitlines()
    if len(lines) > max_lines:
        return (
            "\n".join(lines[:max_lines])
            + f"\n... (truncated {len(lines) - max_lines} lines) ...\n"
        )

    return diff_content


def get_smart_diff(staged=True, target_branch=None):
    # Get list of changed files
    cmd = ["diff", "--name-only"]
    if staged:
        cmd.append("--staged")
    elif target_branch:
        cmd.append(f"{target_branch}...HEAD")

    files_output = run_git_command(cmd)
    if not files_output:
        return None

    files = files_output.splitlines()
    if not files:
        return None

    # Build summary
    summary = "Changes Summary:\n"
    for f in files:
        summary += f"- {f}\n"
    summary += "\nDetailed Diffs:\n"

    detailed_diffs = []
    for f in files:
        if is_excluded_file(f):
            detailed_diffs.append(f"File: {f}\n[Skipped binary/lock/generated file]\n")
            continue

        diff = get_file_diff(f, staged, target_branch)
        if diff:
            detailed_diffs.append(f"File: {f}\n{diff}\n")

    return summary + "\n".join(detailed_diffs)


def handle_cm(args):
    # Get status to show user what is being committed (mimic README)
    status_output = run_git_command(["status"])
    print(status_output)
    print()

    # Get diff
    diff_output = get_smart_diff(staged=True)

    if not diff_output:
        print("No changes detected.")
        return

    prompt = get_template_content("PROMPT_COMMIT.md")

    print(f"Generating commit message suggestions using {args.model}...")
    response = run_gemini(prompt, diff_output, args, args.model)

    print("\nChoose commit message:")
    print(response)

    # Simple selection logic assuming response format [1] ...
    # For now, just print logic as requested.
    # The README implies an interactive prompt "> 1"

    try:
        choice = input("> ")
    except KeyboardInterrupt:
        print("\nCanceled.")
        return

    # Check if choice corresponds to an option (parsing response)
    # The README says:
    # [1] hogehoge
    # ...
    # > 1
    # Committed!

    # We need to extract the message corresponding to choice.
    # This is tricky because the output from LLM might vary.
    # We will try to parse line by line.

    lines = response.splitlines()
    selected_message = ""

    # Very naive parsing: look for lines starting with [{choice}]
    found = False
    for line in lines:
        if line.strip().startswith(f"[{choice}]"):
            selected_message = line.split(f"[{choice}]", 1)[1].strip()
            found = True
            break

    if found:
        print(f"Committing with message: {selected_message}")
        try:
            subprocess.run(["git", "commit", "-m", selected_message], check=True)
            print("Committed!")
        except subprocess.CalledProcessError:
            print("Commit failed.")
    elif choice.strip() == "4" or choice.lower() == "cancel":  # Assuming 4 is Cancel
        print("Canceled.")
    else:
        print("Invalid selection or parsing failed. Please manually commit.")


def handle_pr(args):
    print("Generating pull request suggestions...")

    target_branch = "main"  # Default
    # Check if main exists, if not try master?
    # Simple check:
    branches = run_git_command(["branch", "-a"])
    if "main" not in branches and "master" in branches:
        target_branch = "master"

    diff_output = get_smart_diff(staged=False, target_branch=target_branch)

    if not diff_output:
        print("No differences found against target branch.")
        return

    prompt = get_template_content("PROMPT_PULL_REQUEST.md")

    response = run_gemini(prompt, diff_output, args, args.model)

    print("\nChoose pull request title and body:")
    print(response)

    try:
        choice = input("> ")
    except KeyboardInterrupt:
        print("\nCanceled.")
        return

    # Parsing PR is harder because it's multiline.
    # [1] Title
    #
    # Body
    # ...

    if choice.lower() == "cancel" or (
        choice.isdigit() and int(choice) >= 3
    ):  # Assuming last is cancel? 3 in example.
        print("Canceled.")
        return

    sections = response.split("[")
    selected_section = None
    for section in sections:
        if section.startswith(f"{choice}]"):
            selected_section = section
            break

    if selected_section:
        # Extract title and body
        # Format: 1] Title \n\n Body...
        content = selected_section.split("]", 1)[1].strip()
        lines = content.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        print(f"\nTitle: {title}")
        print(f"Body:\n{body}")

        try:
            # check if gh is installed
            subprocess.run(["gh", "--version"], capture_output=True, check=True)

            # create PR
            subprocess.run(["gh", "pr", "create", "-t", title, "-b", body], check=True)
            print("Created pull request!")
        except FileNotFoundError:
            print(
                "Error: 'gh' CLI not found. Please install GitHub CLI.", file=sys.stderr
            )
        except subprocess.CalledProcessError as e:
            print(f"Error creating PR: {e}", file=sys.stderr)

    else:
        print("Invalid selection.")


def main():
    # Parent parser for common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model to use (default: gemini-2.5-flash)",
    )
    parent_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    parser = argparse.ArgumentParser(description="Git AI Suggest CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("m", parents=[parent_parser], help="Suggest commit message")
    subparsers.add_parser(
        "p", parents=[parent_parser], help="Suggest pull request title and body"
    )

    args = parser.parse_args()

    if args.command == "m":
        handle_cm(args)
    elif args.command == "p":
        handle_pr(args)


if __name__ == "__main__":
    main()
