"""Framework path resolution utilities"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def resolve_framework_path(framework_name: str, env_var_path: Optional[Path] = None) -> str:
    """Resolve framework path using priority: env var → bundled → development mode

    Args:
        framework_name: Name of the framework (e.g., "xcdb")
        env_var_path: Optional explicit path from environment variable

    Returns:
        Absolute path to the framework binary

    Raises:
        FileNotFoundError: If framework cannot be found in any location
    """
    logger.debug(f"Resolving framework path for: {framework_name}")

    # Priority 1: Environment variable
    if env_var_path:
        if env_var_path.exists():
            logger.info(f"Using framework from environment variable: {env_var_path}")
            return str(env_var_path)
        else:
            logger.warning(f"Environment variable path does not exist: {env_var_path}")

    # Priority 2: Bundled framework
    # Path relative to this module: <package>/frameworks/<name>.framework/<name>
    package_root = Path(__file__).parent.parent.parent.parent
    bundled_path = package_root / "frameworks" / f"{framework_name}.framework" / framework_name

    if bundled_path.exists():
        logger.info(f"Using bundled framework: {bundled_path}")
        return str(bundled_path)

    # Priority 3: Development mode
    # Check if xcdb project exists in common development locations
    dev_locations = [
        Path.home() / "Projects" / framework_name / "build" / f"{framework_name}.framework" / framework_name,
        Path.home() / "Developer" / framework_name / "build" / f"{framework_name}.framework" / framework_name,
        Path.home() / framework_name / "build" / f"{framework_name}.framework" / framework_name,
    ]

    for dev_path in dev_locations:
        if dev_path.exists():
            logger.info(f"Using development framework: {dev_path}")
            return str(dev_path)

    # Not found in any location
    error_msg = f"Framework '{framework_name}' not found. Searched:\n"
    if env_var_path:
        error_msg += f"  - Environment variable: {env_var_path}\n"
    error_msg += f"  - Bundled: {bundled_path}\n"
    for dev_path in dev_locations:
        error_msg += f"  - Development: {dev_path}\n"
    error_msg += f"\nTo use a custom path, provide the full path to the framework binary when calling lldb_load_framework"

    raise FileNotFoundError(error_msg)
