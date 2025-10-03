#!/usr/bin/env python3
"""Build and publish immutable container images for TTRPG Center services.

This script replaces the GitHub Actions build stage. It can be executed in any
container-capable CI runner (e.g., container-with-2) and will:

1. Build service images for the requested environments.
2. Tag each image as <registry>/<repository>:<tag> where <tag> defaults to
   YYYYMMDD.<git-sha>.
3. Push the image (unless --no-push is supplied).
4. Resolve the pushed digest and write env/<env>/images.lock files containing
   the exact image references (tag + @sha256 digest).

Usage examples
--------------
# Build and push images for dev + test into ghcr.io/ttrpg-center
scripts/registry/build-images.py --env dev --env test --registry ghcr.io/ttrpg-center

# Perform a dry run build for dev only, without pushing
scripts/registry/build-images.py --env dev --no-push --tag 20241002.local
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = "ghcr.io/ttrpg-center"
ZERO_DIGEST = "0" * 64


@dataclass(frozen=True)
class ServiceDefinition:
    key: str  # logical identifier (ingest, admin-ui, etc.)
    repository: str  # registry repository name
    context: Path
    dockerfile: Path
    build_args: Tuple[Tuple[str, str], ...] = ()

    def build_command(self, tag: str) -> List[str]:
        cmd = [
            "docker",
            "build",
            "--pull",
            "--tag",
            tag,
            "--file",
            str(self.dockerfile),
        ]
        for arg, value in self.build_args:
            cmd.extend(["--build-arg", f"{arg}={value}"])
        cmd.append(str(self.context))
        return cmd


SERVICE_DEFINITIONS: Dict[str, ServiceDefinition] = {
    "ingest": ServiceDefinition(
        key="ingest",
        repository="ingest",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "ingest"),),
    ),
    "pipeline_worker": ServiceDefinition(
        key="pipeline_worker",
        repository="pipeline-worker",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "pipeline_worker"),),
    ),
    "orchestrator": ServiceDefinition(
        key="orchestrator",
        repository="orchestrator",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "orchestrator"),),
    ),
    "admin_api": ServiceDefinition(
        key="admin_api",
        repository="admin-api",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "admin_api"),),
    ),
    "user_api": ServiceDefinition(
        key="user_api",
        repository="user-api",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "user_api"),),
    ),
    "source_management": ServiceDefinition(
        key="source_management",
        repository="source-management",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.microservice",
        build_args=(("SERVICE_NAME", "source_management"),),
    ),
    "app": ServiceDefinition(
        key="app",
        repository="app",
        context=ROOT,
        dockerfile=ROOT / "services" / "app" / "Dockerfile",
    ),
    "admin_ui": ServiceDefinition(
        key="admin_ui",
        repository="admin-ui",
        context=ROOT / "web" / "admin-ui",
        dockerfile=ROOT / "web" / "admin-ui" / "Dockerfile",
    ),
    "user_ui": ServiceDefinition(
        key="user_ui",
        repository="user-ui",
        context=ROOT / "web" / "user-ui",
        dockerfile=ROOT / "web" / "user-ui" / "Dockerfile",
    ),
    "test_runner": ServiceDefinition(
        key="test_runner",
        repository="test-runner",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.test-runner",
    ),
    "test_console": ServiceDefinition(
        key="test_console",
        repository="test-console",
        context=ROOT,
        dockerfile=ROOT / "Dockerfile.test-console",
    ),
}

ENVIRONMENT_MATRIX: Dict[str, Dict[str, str]] = {
    "dev": {
        "DEV_INGEST_IMAGE": "ingest",
        "DEV_PIPELINE_WORKER_IMAGE": "pipeline_worker",
        "DEV_ORCHESTRATOR_IMAGE": "orchestrator",
        "DEV_ADMIN_API_IMAGE": "admin_api",
        "DEV_USER_API_IMAGE": "user_api",
        "DEV_SOURCE_MANAGEMENT_IMAGE": "source_management",
        "DEV_ADMIN_UI_IMAGE": "admin_ui",
        "DEV_USER_UI_IMAGE": "user_ui",
        "DEV_APP_IMAGE": "app",
        "DEV_TEST_RUNNER_IMAGE": "test_runner",
    },
    "test": {
        "TEST_INGEST_IMAGE": "ingest",
        "TEST_ORCHESTRATOR_IMAGE": "orchestrator",
        "TEST_ADMIN_API_IMAGE": "admin_api",
        "TEST_USER_API_IMAGE": "user_api",
        "TEST_APP_IMAGE": "app",
        "TEST_TEST_RUNNER_IMAGE": "test_runner",
        "TEST_TEST_CONSOLE_API_IMAGE": "test_console",
    },
    "prod": {
        "PROD_INGEST_IMAGE": "ingest",
        "PROD_ORCHESTRATOR_IMAGE": "orchestrator",
        "PROD_ADMIN_API_IMAGE": "admin_api",
        "PROD_USER_API_IMAGE": "user_api",
        "PROD_APP_IMAGE": "app",
    },
}


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, text=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - CLI helper
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{exc}") from exc


def capture(cmd: List[str]) -> str:
    result = run(cmd, check=True)
    return result.stdout.strip() if result.stdout else ""


def git_sha() -> str:
    try:
        return capture(["git", "rev-parse", "--short", "HEAD"])
    except SystemExit:
        return "unknown"


def build_and_push(
    definition: ServiceDefinition,
    registry: str,
    tag: str,
    push: bool,
    dry_run: bool,
) -> str:
    image_ref = f"{registry}/{definition.repository}:{tag}"
    if dry_run:
        print(f"[DRY RUN] docker build -> {image_ref}")
        return f"{image_ref}@sha256:{ZERO_DIGEST}"

    print(f"Building {image_ref}")
    run(definition.build_command(image_ref))
    if push:
        print(f"Pushing {image_ref}")
        run(["docker", "push", image_ref])
    inspect = capture(
        ["docker", "image", "inspect", image_ref, "--format", "{{json .RepoDigests}}"]
    )
    try:
        repo_digests = json.loads(inspect)
    except json.JSONDecodeError as exc:  # pragma: no cover - CLI helper
        raise SystemExit(f"Failed to parse docker inspect output for {image_ref}: {inspect}") from exc
    if not repo_digests:
        raise SystemExit(f"No repo digests recorded for {image_ref}. Did you push the image?")
    digest_ref = repo_digests[0]
    print(f"Resolved digest: {digest_ref}")
    return digest_ref


def write_lock_file(env: str, mapping: Dict[str, str]) -> None:
    lock_path = ROOT / "env" / env / "images.lock"
    lines = ["# Auto-generated by scripts/registry/build-images.py", "# Do not edit manually"]
    for key, value in sorted(mapping.items()):
        lines.append(f"{key}={value}")
    lock_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {lock_path} ({len(mapping)} entries)")


def main(argv: Iterable[str]) -> int:
    parser = argparse.ArgumentParser(description="Build immutable service images")
    parser.add_argument(
        "--env",
        dest="environments",
        action="append",
        choices=sorted(ENVIRONMENT_MATRIX.keys()),
        help="Environment(s) to build (default: all)",
    )
    parser.add_argument(
        "--registry",
        default=os.environ.get("TTRPG_REGISTRY", DEFAULT_REGISTRY),
        help=f"Registry/repository root (default: {DEFAULT_REGISTRY})",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Override image tag (default: YYYYMMDD.<git-sha>)",
    )
    parser.add_argument(
        "--no-push",
        dest="push",
        action="store_false",
        help="Build images locally without pushing to the registry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions without building (implies --no-push)",
    )

    args = parser.parse_args(list(argv))
    environments = args.environments or sorted(ENVIRONMENT_MATRIX.keys())
    push = args.push and not args.dry_run
    if args.dry_run:
        push = False

    tag = args.tag
    if not tag:
        today = datetime.datetime.utcnow().strftime("%Y%m%d")
        tag = f"{today}.{git_sha()}"

    registry = args.registry.rstrip('/')

    print(f"Target registry: {registry}")
    print(f"Image tag: {tag}")
    print(f"Environments: {', '.join(environments)}")
    print(f"Push enabled: {push}")

    env_to_digest: Dict[str, Dict[str, str]] = {env: {} for env in environments}
    built_cache: Dict[str, str] = {}

    for env in environments:
        matrix = ENVIRONMENT_MATRIX[env]
        for env_var, service_key in matrix.items():
            definition = SERVICE_DEFINITIONS[service_key]
            if service_key not in built_cache:
                digest_ref = build_and_push(definition, registry, tag, push, args.dry_run)
                built_cache[service_key] = digest_ref
            env_to_digest[env][env_var] = built_cache[service_key]

    if args.dry_run:
        for env, mapping in env_to_digest.items():
            print(f"[DRY RUN] {env} images.lock would contain:")
            for key, value in sorted(mapping.items()):
                print(f"  {key}={value}")
        return 0

    for env, mapping in env_to_digest.items():
        write_lock_file(env, mapping)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main(sys.argv[1:]))
