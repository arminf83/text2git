#!/usr/bin/env python3

import os
import sys
import base64
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

API_URL = os.getenv(
    "GITHUB_API_URL",
    "https://api.github.com"
).rstrip("/")

API_VERSION = os.getenv(
    "GITHUB_API_VERSION",
    "2026-03-10"
)

USER_AGENT = "github-ocr-uploader/1.0"

TESSERACT_LANG = os.getenv(
    "TESSERACT_LANG",
    "eng"
)

TESSERACT_CONFIG = os.getenv(
    "TESSERACT_CONFIG",
    ""
)

# فقط این فرمت‌ها مجاز هستند
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp"
}

WARN_FILE_SIZE = int(
    os.getenv(
        "WARN_FILE_SIZE_MB",
        "50"
    )
) * 1024 * 1024

MAX_FILE_SIZE = int(
    os.getenv(
        "MAX_FILE_SIZE_MB",
        "100"
    )
) * 1024 * 1024


EXCLUDED_DIRS = {
    x.strip()
    for x in os.getenv(
        "EXCLUDED_DIRS",
        ".git,__pycache__,.venv,venv,node_modules"
    ).split(",")
    if x.strip()
}

EXCLUDED_FILES = {
    x.strip()
    for x in os.getenv(
        "EXCLUDED_FILES",
        ".env,.env.local,.env.production"
    ).split(",")
    if x.strip()
}


# ============================================================
# COLORS
# ============================================================

class Colors:

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


def info(message):
    print(
        f"{Colors.BLUE}[INFO]{Colors.RESET} {message}"
    )


def success(message):
    print(
        f"{Colors.GREEN}[OK]{Colors.RESET} {message}"
    )


def warning(message):
    print(
        f"{Colors.YELLOW}[WARNING]{Colors.RESET} {message}"
    )


def error(message):
    print(
        f"{Colors.RED}[ERROR]{Colors.RESET} {message}"
    )


def title(message):

    print()

    print(
        f"{Colors.CYAN}"
        f"{Colors.BOLD}"
        f"{'=' * 70}"
        f"{Colors.RESET}"
    )

    print(
        f"{Colors.CYAN}"
        f"{Colors.BOLD}"
        f"{message}"
        f"{Colors.RESET}"
    )

    print(
        f"{Colors.CYAN}"
        f"{Colors.BOLD}"
        f"{'=' * 70}"
        f"{Colors.RESET}"
    )


# ============================================================
# GITHUB CLIENT
# ============================================================

class GitHubClient:

    def __init__(self, token):

        self.token = token

        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        })


    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    def request(
        self,
        method,
        endpoint,
        **kwargs
    ):

        url = f"{API_URL}{endpoint}"

        try:

            response = self.session.request(
                method,
                url,
                timeout=30,
                **kwargs
            )

        except requests.RequestException as exc:

            raise RuntimeError(
                f"Network error: {exc}"
            ) from exc


        if not response.ok:

            try:

                data = response.json()

                message = data.get(
                    "message",
                    response.text
                )

            except Exception:

                message = response.text

            raise RuntimeError(
                f"GitHub API error "
                f"[{response.status_code}]: "
                f"{message}"
            )


        if not response.content:

            return None


        try:

            return response.json()

        except Exception:

            return response.text


    # --------------------------------------------------------
    # CURRENT USER
    # --------------------------------------------------------

    def get_current_user(self):

        return self.request(
            "GET",
            "/user"
        )


    # --------------------------------------------------------
    # REPOSITORIES
    # --------------------------------------------------------

    def get_repositories(self):

        repositories = []

        page = 1

        while True:

            data = self.request(
                "GET",
                "/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "affiliation":
                        "owner,collaborator,"
                        "organization_member",
                    "sort": "full_name",
                    "direction": "asc",
                }
            )

            if not data:

                break

            repositories.extend(data)

            if len(data) < 100:

                break

            page += 1


        repositories = [
            repo
            for repo in repositories
            if repo.get(
                "permissions",
                {}
            ).get(
                "push"
            ) is True
        ]

        return repositories


    # --------------------------------------------------------
    # BRANCHES
    # --------------------------------------------------------

    def get_branches(
        self,
        owner,
        repo
    ):

        branches = []

        page = 1

        while True:

            data = self.request(
                "GET",
                f"/repos/{owner}/{repo}/branches",
                params={
                    "per_page": 100,
                    "page": page,
                }
            )

            if not data:

                break

            branches.extend(data)

            if len(data) < 100:

                break

            page += 1

        return branches


    # --------------------------------------------------------
    # BRANCH
    # --------------------------------------------------------

    def get_branch(
        self,
        owner,
        repo,
        branch
    ):

        encoded_branch = quote(
            branch,
            safe=""
        )

        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/branches/"
            f"{encoded_branch}"
        )


    # --------------------------------------------------------
    # COMMIT
    # --------------------------------------------------------

    def get_commit(
        self,
        owner,
        repo,
        sha
    ):

        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/git/commits/{sha}"
        )


    # --------------------------------------------------------
    # CREATE BLOB
    # --------------------------------------------------------

    def create_blob(
        self,
        owner,
        repo,
        file_path
    ):

        with open(
            file_path,
            "rb"
        ) as file:

            content = file.read()


        encoded_content = base64.b64encode(
            content
        ).decode("ascii")


        return self.request(
            "POST",
            f"/repos/{owner}/{repo}/git/blobs",
            json={
                "content": encoded_content,
                "encoding": "base64",
            }
        )


    # --------------------------------------------------------
    # CREATE TREE
    # --------------------------------------------------------

    def create_tree(
        self,
        owner,
        repo,
        base_tree_sha,
        tree_entries
    ):

        return self.request(
            "POST",
            f"/repos/{owner}/{repo}/git/trees",
            json={
                "base_tree": base_tree_sha,
                "tree": tree_entries,
            }
        )


    # --------------------------------------------------------
    # CREATE COMMIT
    # --------------------------------------------------------

    def create_commit(
        self,
        owner,
        repo,
        message,
        tree_sha,
        parent_sha
    ):

        return self.request(
            "POST",
            f"/repos/{owner}/{repo}/git/commits",
            json={
                "message": message,
                "tree": tree_sha,
                "parents": [
                    parent_sha
                ],
            }
        )


    # --------------------------------------------------------
    # UPDATE BRANCH
    # --------------------------------------------------------

    def update_branch(
        self,
        owner,
        repo,
        branch,
        commit_sha
    ):

        encoded_branch = quote(
            branch,
            safe=""
        )

        return self.request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/heads/"
            f"{encoded_branch}",
            json={
                "sha": commit_sha,
                "force": False,
            }
        )


# ============================================================
# TOKEN
# ============================================================

def get_token():

    token = os.getenv(
        "GITHUB_TOKEN"
    )

    if not token:

        error(
            "GITHUB_TOKEN was not found in .env"
        )

        print()

        print(
            "Create a .env file next to "
            "github_ocr_uploader.py:"
        )

        print()

        print(
            "GITHUB_TOKEN=github_pat_xxxxxxxxxxxxx"
        )

        print()

        sys.exit(1)

    return token.strip()


# ============================================================
# TESSERACT CHECK
# ============================================================

def check_tesseract():

    info(
        "Checking Tesseract installation..."
    )

    try:

        result = subprocess.run(
            [
                "tesseract",
                "--version"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

    except FileNotFoundError:

        raise RuntimeError(
            "Tesseract was not found.\n"
            "Install it with:\n"
            "sudo apt install tesseract-ocr"
        )

    except subprocess.SubprocessError as exc:

        raise RuntimeError(
            f"Could not execute Tesseract: {exc}"
        )


    if result.returncode != 0:

        raise RuntimeError(
            "Tesseract installation check failed."
        )


    first_line = (
        result.stdout.strip().splitlines()
    )

    if first_line:

        success(
            f"Tesseract found: "
            f"{first_line[0]}"
        )

    else:

        success(
            "Tesseract found."
        )


# ============================================================
# CHECK TESSERACT LANGUAGE
# ============================================================

def check_tesseract_language():

    info(
        f"Checking Tesseract language: "
        f"{TESSERACT_LANG}"
    )

    try:

        result = subprocess.run(
            [
                "tesseract",
                "--list-langs"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

    except subprocess.SubprocessError as exc:

        raise RuntimeError(
            f"Could not list Tesseract languages: {exc}"
        )


    if result.returncode != 0:

        raise RuntimeError(
            "Could not read Tesseract languages."
        )


    installed_languages = set()

    for line in result.stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith(
            "List of available languages"
        ):
            continue

        installed_languages.add(line)


    requested_languages = TESSERACT_LANG.split("+")

    missing_languages = [
        language
        for language in requested_languages
        if language not in installed_languages
    ]


    if missing_languages:

        raise RuntimeError(
            "The following Tesseract language(s) "
            "are not installed: "
            + ", ".join(missing_languages)
        )


    success(
        f"Tesseract language available: "
        f"{TESSERACT_LANG}"
    )


# ============================================================
# IMAGE SCANNER
# ============================================================

def scan_images(source_dir):

    images = []

    source_dir = source_dir.resolve()

    for root, dirs, filenames in os.walk(
        source_dir
    ):

        dirs[:] = [
            directory
            for directory in dirs
            if directory not in EXCLUDED_DIRS
        ]


        for filename in filenames:

            if filename in EXCLUDED_FILES:

                continue


            file_path = Path(root) / filename


            # فقط فایل تصویری
            if file_path.suffix.lower() not in IMAGE_EXTENSIONS:

                continue


            try:

                relative_path = file_path.relative_to(
                    source_dir
                )

            except ValueError:

                continue


            images.append(
                (
                    file_path,
                    relative_path
                )
            )


    # مرتب‌سازی بر اساس مسیر
    images.sort(
        key=lambda item: str(
            item[1]
        ).lower()
    )


    return images


# ============================================================
# HUMAN READABLE SIZE
# ============================================================

def human_size(size):

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ]

    value = float(size)

    for unit in units:

        if value < 1024:

            return (
                f"{value:.2f} {unit}"
            )

        value /= 1024

    return f"{value:.2f} PB"


# ============================================================
# OCR SINGLE IMAGE
# ============================================================

def ocr_image(image_path):

    command = [
        "tesseract",
        str(image_path),
        "stdout",
        "-l",
        TESSERACT_LANG
    ]


    if TESSERACT_CONFIG:

        command.extend(
            TESSERACT_CONFIG.split()
        )


    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "OCR timed out after 300 seconds."
        )

    except FileNotFoundError:

        raise RuntimeError(
            "Tesseract was not found."
        )

    except subprocess.SubprocessError as exc:

        raise RuntimeError(
            f"Tesseract execution failed: {exc}"
        )


    if result.returncode != 0:

        stderr = result.stderr.strip()

        if stderr:

            raise RuntimeError(stderr)

        raise RuntimeError(
            f"Tesseract exited with code "
            f"{result.returncode}"
        )


    return result.stdout.strip()


# ============================================================
# GENERATE MARKDOWN
# ============================================================

def generate_markdown(
    source_dir,
    images,
    timestamp
):

    folder_name = source_dir.name

    markdown = []

    markdown.append(
        "# OCR Results"
    )

    markdown.append("")

    markdown.append(
        f"**Source Directory:** `{folder_name}`"
    )

    markdown.append(
        f"**Generated:** `{timestamp}`"
    )

    markdown.append(
        f"**Images:** `{len(images)}`"
    )

    markdown.append("")

    markdown.append("---")

    markdown.append("")


    successful = 0
    failed = 0


    for index, (
        image_path,
        relative_path
    ) in enumerate(
        images,
        start=1
    ):

        print()

        print(
            f"{Colors.CYAN}"
            f"[{index}/{len(images)}]"
            f"{Colors.RESET} "
            f"{relative_path}"
        )


        markdown.append(
            f"## {relative_path}"
        )

        markdown.append("")


        try:

            text = ocr_image(
                image_path
            )

            successful += 1

            if text:

                markdown.append(text)

            else:

                markdown.append(
                    "_No text was detected in this image._"
                )


            success(
                "OCR completed."
            )


        except Exception as exc:

            failed += 1

            warning(
                f"OCR failed: {exc}"
            )

            markdown.append(
                f"**OCR Error:** `{exc}`"
            )


        markdown.append("")

        markdown.append("---")

        markdown.append("")


    return (
        "\n".join(markdown),
        successful,
        failed
    )


# ============================================================
# SAVE MARKDOWN
# ============================================================

def save_markdown(
    source_dir,
    timestamp,
    content
):

    safe_folder_name = source_dir.name

    filename = (
        f"{safe_folder_name}_"
        f"{timestamp.replace(':', '-')}.md"
    )


    output_path = (
        source_dir.parent / filename
    )


    try:

        output_path.write_text(
            content,
            encoding="utf-8"
        )

    except OSError as exc:

        raise RuntimeError(
            f"Could not create Markdown file: {exc}"
        )


    return output_path


# ============================================================
# REPOSITORY SELECTION
# ============================================================

def select_repository(repositories):

    title(
        "Available GitHub Repositories"
    )


    if not repositories:

        error(
            "No writable repositories were found."
        )

        sys.exit(1)


    for index, repo in enumerate(
        repositories,
        start=1
    ):

        private_text = (
            "PRIVATE"
            if repo.get("private")
            else "PUBLIC"
        )

        default_branch = repo.get(
            "default_branch",
            "?"
        )


        print(
            f"{Colors.GREEN}"
            f"{index:3}."
            f"{Colors.RESET} "
            f"{repo['full_name']} "
            f"[{private_text}] "
            f"[default: {default_branch}]"
        )


    print()


    while True:

        choice = input(
            "Select repository number: "
        ).strip()


        try:

            number = int(choice)

            if 1 <= number <= len(repositories):

                return repositories[
                    number - 1
                ]

        except ValueError:

            pass


        error(
            "Invalid selection."
        )


# ============================================================
# BRANCH SELECTION
# ============================================================

def select_branch(
    client,
    owner,
    repo,
    default_branch
):

    title(
        "Branch Selection"
    )


    branches = client.get_branches(
        owner,
        repo
    )


    if not branches:

        error(
            "No branches found."
        )

        sys.exit(1)


    for index, branch in enumerate(
        branches,
        start=1
    ):

        branch_name = branch["name"]

        marker = ""

        if branch_name == default_branch:

            marker = " [DEFAULT]"


        print(
            f"{Colors.GREEN}"
            f"{index:3}."
            f"{Colors.RESET} "
            f"{branch_name}"
            f"{marker}"
        )


    print()


    while True:

        choice = input(
            "Select branch number "
            f"(default: {default_branch}): "
        ).strip()


        if not choice:

            return default_branch


        try:

            number = int(choice)

            if 1 <= number <= len(branches):

                return branches[
                    number - 1
                ]["name"]

        except ValueError:

            pass


        error(
            "Invalid branch selection."
        )


# ============================================================
# LOCAL PATH
# ============================================================

def ask_local_path():

    title(
        "Image Directory"
    )


    while True:

        value = input(
            "Enter image directory path: "
        ).strip()


        if not value:

            error(
                "Path cannot be empty."
            )

            continue


        path = Path(
            value
        ).expanduser()


        if not path.exists():

            error(
                "Path does not exist."
            )

            continue


        if not path.is_dir():

            error(
                "Path is not a directory."
            )

            continue


        return path.resolve()


# ============================================================
# GITHUB DESTINATION
# ============================================================

def ask_destination():

    title(
        "GitHub Destination"
    )


    destination = input(
        "Destination directory inside repository "
        "(empty = repository root): "
    ).strip()


    return destination.strip("/")


# ============================================================
# COMMIT MESSAGE
# ============================================================

def ask_commit_message():

    title(
        "Commit Message"
    )


    while True:

        message = input(
            "Commit message: "
        ).strip()


        if message:

            return message


        error(
            "Commit message cannot be empty."
        )


# ============================================================
# BUILD GITHUB PATH
# ============================================================

def build_github_path(
    destination,
    filename
):

    if destination:

        return (
            f"{destination}/{filename}"
        )

    return filename


# ============================================================
# PREVIEW
# ============================================================

def show_preview(
    repository,
    branch,
    local_path,
    destination,
    markdown_path,
    images,
    timestamp,
    commit_message
):

    title(
        "Upload Preview"
    )


    print(
        f"{Colors.BOLD}"
        f"Repository:"
        f"{Colors.RESET} "
        f"{repository['full_name']}"
    )


    print(
        f"{Colors.BOLD}"
        f"Branch:"
        f"{Colors.RESET} "
        f"{branch}"
    )


    print(
        f"{Colors.BOLD}"
        f"Image directory:"
        f"{Colors.RESET} "
        f"{local_path}"
    )


    print(
        f"{Colors.BOLD}"
        f"Images:"
        f"{Colors.RESET} "
        f"{len(images)}"
    )


    print(
        f"{Colors.BOLD}"
        f"Generated file:"
        f"{Colors.RESET} "
        f"{markdown_path.name}"
    )


    github_path = build_github_path(
        destination,
        markdown_path.name
    )


    print(
        f"{Colors.BOLD}"
        f"GitHub path:"
        f"{Colors.RESET} "
        f"/{github_path}"
    )


    print(
        f"{Colors.BOLD}"
        f"Timestamp:"
        f"{Colors.RESET} "
        f"{timestamp}"
    )


    print(
        f"{Colors.BOLD}"
        f"Commit:"
        f"{Colors.RESET} "
        f"{commit_message}"
    )


    print()


    print(
        f"{Colors.CYAN}"
        f"Only the generated Markdown file "
        f"will be uploaded."
        f"{Colors.RESET}"
    )


# ============================================================
# CONFIRMATION
# ============================================================

def ask_confirmation():

    print()


    while True:

        answer = input(
            "Continue with upload? [y/N]: "
        ).strip().lower()


        if answer in (
            "y",
            "yes"
        ):

            return True


        if answer in (
            "n",
            "no",
            ""
        ):

            return False


        print(
            "Please enter y or n."
        )


# ============================================================
# UPLOAD SINGLE MARKDOWN
# ============================================================

def upload_markdown(
    client,
    owner,
    repo,
    branch,
    destination,
    markdown_path,
    commit_message
):

    title(
        "Uploading Markdown"
    )


    # --------------------------------------------------------
    # Get current branch
    # --------------------------------------------------------

    info(
        f"Getting current state of "
        f"branch '{branch}'..."
    )


    branch_data = client.get_branch(
        owner,
        repo,
        branch
    )


    parent_commit_sha = (
        branch_data[
            "commit"
        ][
            "sha"
        ]
    )


    commit_data = client.get_commit(
        owner,
        repo,
        parent_commit_sha
    )


    base_tree_sha = (
        commit_data[
            "tree"
        ][
            "sha"
        ]
    )


    info(
        f"Base commit: {parent_commit_sha}"
    )

    info(
        f"Base tree: {base_tree_sha}"
    )


    # --------------------------------------------------------
    # Create blob
    # --------------------------------------------------------

    github_path = build_github_path(
        destination,
        markdown_path.name
    )


    info(
        f"Uploading: {github_path}"
    )


    blob = client.create_blob(
        owner,
        repo,
        markdown_path
    )


    blob_sha = blob["sha"]


    tree_entries = [
        {
            "path": github_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        }
    ]


    success(
        f"Blob created: {blob_sha}"
    )


    # --------------------------------------------------------
    # Create tree
    # --------------------------------------------------------

    info(
        "Creating Git tree..."
    )


    tree = client.create_tree(
        owner,
        repo,
        base_tree_sha,
        tree_entries
    )


    new_tree_sha = tree["sha"]


    success(
        f"Tree created: {new_tree_sha}"
    )


    # --------------------------------------------------------
    # Create commit
    # --------------------------------------------------------

    info(
        "Creating commit..."
    )


    commit = client.create_commit(
        owner,
        repo,
        commit_message,
        new_tree_sha,
        parent_commit_sha
    )


    new_commit_sha = commit["sha"]


    success(
        f"Commit created: {new_commit_sha}"
    )


    # --------------------------------------------------------
    # Update branch
    # --------------------------------------------------------

    info(
        f"Updating branch '{branch}'..."
    )


    client.update_branch(
        owner,
        repo,
        branch,
        new_commit_sha
    )


    success(
        f"Branch '{branch}' updated successfully."
    )


    return {
        "commit_sha": new_commit_sha,
        "tree_sha": new_tree_sha,
        "github_path": github_path,
    }


# ============================================================
# FINAL REPORT
# ============================================================

def show_final_report(
    repository,
    branch,
    result,
    image_count,
    successful_ocr,
    failed_ocr
):

    title(
        "Upload Completed"
    )


    print(
        f"{Colors.GREEN}"
        f"{Colors.BOLD}"
        "SUCCESS"
        f"{Colors.RESET}"
    )


    print()


    print(
        f"Repository    : "
        f"{repository['full_name']}"
    )


    print(
        f"Branch        : "
        f"{branch}"
    )


    print(
        f"Images        : "
        f"{image_count}"
    )


    print(
        f"OCR successful: "
        f"{successful_ocr}"
    )


    print(
        f"OCR failed    : "
        f"{failed_ocr}"
    )


    print(
        f"Markdown      : "
        f"{result['github_path']}"
    )


    print(
        f"Commit SHA    : "
        f"{result['commit_sha']}"
    )


    print(
        f"Tree SHA      : "
        f"{result['tree_sha']}"
    )


    print()


    print(
        "All OCR results were stored "
        "in a single Markdown file."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    title(
        "GitHub OCR Uploader"
    )


    print(
        "Image directory → Tesseract → "
        "Markdown → GitHub"
    )


    print()


    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )


    # --------------------------------------------------------
    # Token
    # --------------------------------------------------------

    token = get_token()


    # --------------------------------------------------------
    # Tesseract
    # --------------------------------------------------------

    check_tesseract()

    check_tesseract_language()


    # --------------------------------------------------------
    # GitHub Client
    # --------------------------------------------------------

    client = GitHubClient(
        token
    )


    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    info(
        "Authenticating with GitHub..."
    )


    try:

        user = client.get_current_user()

    except Exception as exc:

        error(
            "GitHub authentication failed."
        )

        error(
            str(exc)
        )

        sys.exit(1)


    success(
        f"Authenticated as: "
        f"{user.get('login')}"
    )


    # --------------------------------------------------------
    # Repositories
    # --------------------------------------------------------

    info(
        "Loading repositories..."
    )


    try:

        repositories = client.get_repositories()

    except Exception as exc:

        error(
            "Could not load repositories."
        )

        error(
            str(exc)
        )

        sys.exit(1)


    repository = select_repository(
        repositories
    )


    owner = repository[
        "owner"
    ][
        "login"
    ]


    repo_name = repository[
        "name"
    ]


    # --------------------------------------------------------
    # Branch
    # --------------------------------------------------------

    branch = select_branch(
        client,
        owner,
        repo_name,
        repository.get(
            "default_branch",
            "main"
        )
    )


    # --------------------------------------------------------
    # Local directory
    # --------------------------------------------------------

    local_path = ask_local_path()


    # --------------------------------------------------------
    # Scan images
    # --------------------------------------------------------

    title(
        "Scanning Images"
    )


    info(
        f"Scanning: {local_path}"
    )


    images = scan_images(
        local_path
    )


    if not images:

        error(
            "No supported image files were found."
        )

        print()

        print(
            "Supported formats:"
        )

        print(
            ", ".join(
                sorted(IMAGE_EXTENSIONS)
            )
        )

        sys.exit(1)


    success(
        f"{len(images)} image(s) found."
    )


    # --------------------------------------------------------
    # Generate Markdown
    # --------------------------------------------------------

    title(
        "Running OCR"
    )


    markdown_content, successful_ocr, failed_ocr = (
        generate_markdown(
            local_path,
            images,
            timestamp
        )
    )


    # --------------------------------------------------------
    # Save Markdown
    # --------------------------------------------------------

    title(
        "Creating Markdown"
    )


    markdown_path = save_markdown(
        local_path,
        timestamp,
        markdown_content
    )


    success(
        f"Markdown created: "
        f"{markdown_path}"
    )


    print(
        f"Markdown size: "
        f"{human_size(markdown_path.stat().st_size)}"
    )


    # --------------------------------------------------------
    # Destination
    # --------------------------------------------------------

    destination = ask_destination()


    # --------------------------------------------------------
    # Commit message
    # --------------------------------------------------------

    commit_message = ask_commit_message()


    # --------------------------------------------------------
    # Preview
    # --------------------------------------------------------

    show_preview(
        repository,
        branch,
        local_path,
        destination,
        markdown_path,
        images,
        timestamp,
        commit_message
    )


    # --------------------------------------------------------
    # Confirmation
    # --------------------------------------------------------

    if not ask_confirmation():

        warning(
            "Upload cancelled."
        )

        sys.exit(0)


    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    result = upload_markdown(
        client,
        owner,
        repo_name,
        branch,
        destination,
        markdown_path,
        commit_message
    )


    if not result:

        error(
            "Upload failed."
        )

        sys.exit(1)


    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    show_final_report(
        repository,
        branch,
        result,
        len(images),
        successful_ocr,
        failed_ocr
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        warning(
            "Operation cancelled by user."
        )

        sys.exit(130)

    except Exception as exc:

        print()

        error(
            "Unexpected error:"
        )

        error(
            str(exc)
        )

        sys.exit(1)
