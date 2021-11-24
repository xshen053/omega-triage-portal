import tarfile
import io
from django.core.cache import cache
from packageurl import PackageURL
from azure.storage.blob import BlobServiceClient, BlobClient
from typing import Union, List
import os
import uuid
import triage
import logging
from core.settings import TOOLSHED_BLOB_STORAGE_CONTAINER, TOOLSHED_BLOB_STORAGE_URL
logger = logging.getLogger(__name__)

class AzureBlobStorageAccessor:
    """
    This class is used to access blob stored in the Toolshed container. To use
    it, pass in a name prefix, which is usually {type}/{name}/{version} or
    {type}/{namespace}/{name}/{version}.

    Example:
    >>> blob_storage = AzureBlobStorageAccessor('npm/left-pad/1.3.0')
    >>> blob_storage.get_blob_list()
    >>> blob_storage.get_blob_contents('tool-codeql-results.json')
    """
    def __init__(self, name_prefix: str):
        """Initialize AzureBlobStorageAccessor."""
        if not name_prefix or not name_prefix.strip():
            raise ValueError("name_prefix cannot be empty")
        
        if not TOOLSHED_BLOB_STORAGE_URL or not TOOLSHED_BLOB_STORAGE_CONTAINER:
            raise ValueError("TOOLSHED_BLOB_STORAGE_URL and TOOLSHED_BLOB_CONTAINER must be set")

        self.blob_service = BlobServiceClient(TOOLSHED_BLOB_STORAGE_URL)
        self.container = self.blob_service.get_container_client(TOOLSHED_BLOB_STORAGE_CONTAINER)
        self.name_prefix = name_prefix

    def get_blob_list(self):
        """Get list of blobs in the Toolshed container."""
        try:
            cache_key = f'AzureBlobStorageAccessor[name_prefix={self.name_prefix}].blob_list'
            if cache.has_key(cache_key):
                return cache.get(cache_key)
            else:
                data = list(map(lambda b: {"full_path": b.name, "relative_path": b.name[len(self.name_prefix)+1:]},
                                self.container.list_blobs(name_starts_with=self.name_prefix)))
                cache.set(cache_key, data, timeout=60*60)
                return data
        except:
            logger.exception("Failed to get blob list")
            return []
    
    def get_blob_contents(self, blob_name: str) -> Union[str, bytes]:
        """Load blob contents from Toolshed."""
        try:
            blob = self.container.get_blob_client(blob_name)
            return blob.download_blob().readall()
        except:
            logger.exception("Failed to get blob contents")
            return None

class ToolshedBlobStorageAccessor:
    def __init__(self, scan: 'triage.models.Scan'):
        if not scan:
            raise ValueError("scan cannot be empty")
        self.scan = scan
        package_url = PackageURL.from_string(scan.project_version.package_url)
        name_prefix = self.get_toolshed_prefix(package_url)
        if not name_prefix:
            raise ValueError("Invalid package_url")

        self.blob_accessor = AzureBlobStorageAccessor(name_prefix)

    def get_toolshed_prefix(self, package_url: PackageURL):
        if not package_url:
            return None
        
        if package_url.namespace:
            return f"{package_url.type}/{package_url.namespace}/{package_url.name}/{package_url.version}"
        else:
            return f"{package_url.type}/{package_url.name}/{package_url.version}"

    def get_tool_files(self):
        results = []    # type: List[dict]
        for blob in self.blob_accessor.get_blob_list():
            if blob.get('relative_path').startswith('tool-'):
                results.append({
                    "full_path": blob.get('full_path'),
                    "relative_path": "tools/" + blob.get("relative_path")
                })
        return results

    def get_package_files(self):
        results = []
        for blob in self.blob_accessor.get_blob_list():
            if blob.get('relative_path').startswith('reference-binaries'):
                if blob.get('relative_path').endswith('.tgz'):
                    
                    contents = self.blob_accessor.get_blob_contents(blob.get('full_path'))
                    tar = tarfile.open(fileobj=io.BytesIO(contents), mode='r')
                    for member in tar.getmembers():
                        results.append({
                            "full_path": f"{blob.get('full_path')}:{member.name}",
                            "relative_path": "package/" + member.name
                        })
        return results

    def get_intermediate_files(self):
        return []