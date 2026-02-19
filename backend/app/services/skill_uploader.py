"""
Skill Uploader Service

Manages uploading skills to Anthropic Skills API with caching.
Uploads skill once per session, caches the skill_id to avoid re-uploads.

Cost optimization:
- Upload only once, cache skill_id locally
- Reuse cached skill_id across requests
- Verify skill exists before using cached ID
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Tuple
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class SkillUploader:
    """Upload and cache Skills to Anthropic API"""

    # Cache file stores skill_id mappings
    CACHE_FILE = Path("skills/.skill_cache.json")

    def __init__(self, client: Anthropic, skills_path: Path):
        """
        Initialize SkillUploader

        Args:
            client: Anthropic API client
            skills_path: Path to skills directory (e.g., 'skills/')
        """
        self.client = client
        self.skills_path = Path(skills_path)
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cached skill IDs from disk"""
        if self.CACHE_FILE.exists():
            try:
                return json.loads(self.CACHE_FILE.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load skill cache: {e}. Starting fresh.")
                return {}
        return {}

    def _save_cache(self):
        """Save skill IDs to cache file"""
        try:
            # Ensure cache directory exists
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.CACHE_FILE.write_text(json.dumps(self._cache, indent=2))
            logger.info(f"Skill cache saved to {self.CACHE_FILE}")
        except IOError as e:
            logger.error(f"Failed to save skill cache: {e}")

    def _verify_skill_exists(self, skill_id: str) -> bool:
        """
        Verify a cached skill still exists on Anthropic

        Args:
            skill_id: Skill ID to verify

        Returns:
            True if skill exists, False otherwise
        """
        try:
            self.client.beta.skills.retrieve(
                skill_id=skill_id,
                betas=["skills-2025-10-02"]
            )
            return True
        except Exception as e:
            logger.warning(f"Cached skill {skill_id} no longer exists: {e}")
            return False

    def get_or_upload_skill(self, skill_name: str) -> str:
        """
        Get cached skill_id or upload skill and cache it

        Args:
            skill_name: Skill directory name (e.g., "pnl-statement")

        Returns:
            skill_id: The Anthropic skill ID

        Raises:
            ValueError: If skill directory doesn't exist
            Exception: If upload fails
        """
        # Check if we have a cached skill_id
        if skill_name in self._cache:
            skill_id = self._cache[skill_name]
            logger.info(f"Found cached skill ID for '{skill_name}': {skill_id}")

            # Verify it still exists
            if self._verify_skill_exists(skill_id):
                logger.info(f"Using cached skill: {skill_name}")
                return skill_id
            else:
                logger.info(f"Cached skill deleted, re-uploading: {skill_name}")
                # Remove from cache and re-upload
                del self._cache[skill_name]
                self._save_cache()

        # Upload skill
        return self._upload_skill(skill_name)

    def _collect_skill_files(self, skill_path: Path) -> List[Tuple[str, bytes, str]]:
        """
        Collect all files from skill directory for upload

        Args:
            skill_path: Path to skill directory

        Returns:
            List of tuples: (relative_path, file_content, mime_type)
        """
        files = []

        for root, _, filenames in os.walk(skill_path):
            for filename in filenames:
                # Skip hidden files and cache
                if filename.startswith('.') or filename == '__pycache__':
                    continue

                file_path = Path(root) / filename
                relative_path = file_path.relative_to(skill_path.parent)

                # Determine mime type
                mime_type = self._get_mime_type(filename)

                # Read file content
                try:
                    if mime_type.startswith('text/') or filename.endswith('.md') or filename.endswith('.py'):
                        content = file_path.read_bytes()
                    else:
                        content = file_path.read_bytes()

                    files.append((str(relative_path), content, mime_type))
                    logger.debug(f"Collected file: {relative_path} ({mime_type})")
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")

        return files

    def _get_mime_type(self, filename: str) -> str:
        """Get mime type for file"""
        ext = filename.lower().split('.')[-1]
        mime_types = {
            'md': 'text/markdown',
            'py': 'text/x-python',
            'txt': 'text/plain',
            'json': 'application/json',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'csv': 'text/csv',
        }
        return mime_types.get(ext, 'application/octet-stream')

    def _upload_skill(self, skill_name: str) -> str:
        """
        Upload a skill to Anthropic API

        Args:
            skill_name: Skill directory name

        Returns:
            skill_id: The uploaded skill's ID

        Raises:
            ValueError: If skill directory doesn't exist
            Exception: If upload fails
        """
        skill_path = self.skills_path / skill_name

        # Validate skill directory exists
        if not skill_path.exists():
            raise ValueError(f"Skill directory not found: {skill_path}")

        # Validate SKILL.md exists
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"SKILL.md not found in {skill_path}")

        logger.info(f"Uploading skill '{skill_name}' from {skill_path}")

        try:
            # Collect all files from skill directory
            skill_files = self._collect_skill_files(skill_path)

            if not skill_files:
                raise ValueError(f"No files found in skill directory: {skill_path}")

            logger.info(f"Collected {len(skill_files)} files for upload")

            # Prepare files for upload
            files_for_upload = []
            for relative_path, content, mime_type in skill_files:
                files_for_upload.append((
                    relative_path,  # filename with path
                    content,        # file content
                    mime_type       # mime type
                ))

            # Upload skill to Anthropic
            skill = self.client.beta.skills.create(
                display_title=skill_name.replace("-", " ").title(),
                files=files_for_upload,
                betas=["skills-2025-10-02"]
            )

            logger.info(f"Successfully uploaded skill: {skill.id}")

            # Cache the skill_id
            self._cache[skill_name] = skill.id
            self._save_cache()

            return skill.id

        except Exception as e:
            logger.error(f"Failed to upload skill '{skill_name}': {e}")
            raise

    def delete_skill(self, skill_name: str) -> bool:
        """
        Delete a skill from Anthropic and remove from cache

        Args:
            skill_name: Skill directory name

        Returns:
            True if deleted successfully, False if not found
        """
        if skill_name not in self._cache:
            logger.warning(f"Skill '{skill_name}' not in cache")
            return False

        skill_id = self._cache[skill_name]

        try:
            # First, delete all versions
            versions = self.client.beta.skills.versions.list(
                skill_id=skill_id,
                betas=["skills-2025-10-02"]
            )

            for version in versions.data:
                self.client.beta.skills.versions.delete(
                    skill_id=skill_id,
                    version=version.version,
                    betas=["skills-2025-10-02"]
                )
                logger.info(f"Deleted version {version.version} of skill {skill_id}")

            # Then delete the skill itself
            self.client.beta.skills.delete(
                skill_id=skill_id,
                betas=["skills-2025-10-02"]
            )

            logger.info(f"Deleted skill: {skill_id}")

            # Remove from cache
            del self._cache[skill_name]
            self._save_cache()

            return True

        except Exception as e:
            logger.error(f"Failed to delete skill '{skill_name}': {e}")
            return False

    def list_cached_skills(self) -> dict:
        """
        List all cached skills

        Returns:
            Dictionary of skill_name -> skill_id
        """
        return self._cache.copy()

    def clear_cache(self):
        """Clear the skill cache (doesn't delete skills from Anthropic)"""
        self._cache = {}
        self._save_cache()
        logger.info("Skill cache cleared")
