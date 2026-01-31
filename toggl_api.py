"""Toggl API integration for marking entries as billed."""

import requests
from typing import Optional

from parser import TogglEntry


class TogglAPI:
    """Client for Toggl API operations."""

    BASE_URL = "https://api.track.toggl.com/api/v9"
    BILLED_TAG = "gem-billed"

    def __init__(self, api_token: str, workspace_id: int):
        self.api_token = api_token
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.auth = (api_token, "api_token")
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def get_workspace_id(self) -> Optional[int]:
        """Get the default workspace ID for the authenticated user."""
        response = self.session.get(f"{self.BASE_URL}/me")
        if response.status_code == 200:
            data = response.json()
            return data.get("default_workspace_id")
        return None

    def get_or_create_tag(self) -> Optional[int]:
        """Get or create the 'gem-billed' tag and return its ID."""
        # List existing tags
        response = self.session.get(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/tags"
        )

        if response.status_code == 200:
            tags = response.json()
            for tag in tags:
                if tag.get("name") == self.BILLED_TAG:
                    return tag.get("id")

        # Create the tag if it doesn't exist
        response = self.session.post(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/tags",
            json={"name": self.BILLED_TAG}
        )

        if response.status_code in (200, 201):
            return response.json().get("id")

        return None

    def add_tag_to_entry(self, entry_id: int, tag_ids: list[int]) -> bool:
        """Add tags to a time entry."""
        response = self.session.put(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/time_entries/{entry_id}",
            json={"tag_ids": tag_ids, "tag_action": "add"}
        )
        return response.status_code == 200

    def mark_entries_as_billed(
        self,
        entries: list[TogglEntry],
        progress_callback: Optional[callable] = None
    ) -> tuple[int, int]:
        """
        Mark entries as billed by adding the 'gem-billed' tag.

        Returns: (success_count, failure_count)
        """
        tag_id = self.get_or_create_tag()
        if tag_id is None:
            return (0, len(entries))

        success = 0
        failed = 0

        for i, entry in enumerate(entries):
            if entry.original_id is None:
                failed += 1
                continue

            if self.add_tag_to_entry(entry.original_id, [tag_id]):
                success += 1
            else:
                failed += 1

            if progress_callback:
                progress_callback(i + 1, len(entries))

        return (success, failed)


def create_toggl_client(api_token: str) -> Optional[TogglAPI]:
    """Create a Toggl API client with auto-detected workspace ID."""
    # First, get the workspace ID
    session = requests.Session()
    session.auth = (api_token, "api_token")

    response = session.get(f"{TogglAPI.BASE_URL}/me")
    if response.status_code != 200:
        return None

    data = response.json()
    workspace_id = data.get("default_workspace_id")

    if workspace_id is None:
        return None

    return TogglAPI(api_token, workspace_id)
