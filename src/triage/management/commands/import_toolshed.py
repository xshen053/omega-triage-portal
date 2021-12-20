import json
import logging
import re

from azure.storage.blob import BlobServiceClient
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from packageurl import PackageURL

from core.settings import (
    TOOLSHED_BLOB_STORAGE_CONTAINER_SECRET,
    TOOLSHED_BLOB_STORAGE_URL_SECRET,
)
from triage.util.finding_importers.sarif_importer import SARIFImporter

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Imports a project from the Toolshed repository"

    def add_arguments(self, parser):
        """Assembles arguments to the command."""
        parser.add_argument("--package", required=False, type=str, help="URL (PackageURL format)")
        parser.add_argument(
            "--import-all", required=False, action="store_true", help="SARIF file to load"
        )
        parser.add_argument(
            "--maximum", required=False, type=int, help="Maximum number of entries to import"
        )

    def handle(self, *args, **options):
        """Handle the 'import sarif' command."""
        package = options.get("package")
        if not package and not options.get("import_all"):
            raise ValueError("Must specify either --package or --import-all")

        importer = SARIFImporter()
        self.initialize_toolshed()
        user = get_user_model().objects.get(pk=1)

        if package:
            package_url = PackageURL.from_string(package)
            if package_url.namespace:
                prefix = f"{package_url.type}/{package_url.namespace}/{package_url.name}/{package_url.version}"
            else:
                prefix = f"{package_url.type}/{package_url.name}/{package_url.version}"
            blobs = self.container.list_blobs(name_starts_with=prefix)
        elif options.get("import_all"):
            package_url = None
            blobs = self.container.list_blobs()
        else:
            raise ValueError("Must specify either --package or --import-all")

        num_imported = 0
        for blob in blobs:  # type: BlobProperties
            print(f"Importing {blob.name}")
            num_imported += 1
            if num_imported > options.get("maximum", 0) > 0:
                logger.info("Maximum number of entries reached")
                break

            if blob.name.endswith(".sarif"):
                print(f"Importing {blob.name}")
                logger.debug("Importing %s", blob.name)

                if not package_url:
                    package_url = self.filename_to_package_url(blob.name)
                try:
                    sarif = json.loads(self.container.download_blob(blob.name).content_as_text())
                    importer.import_sarif_file(package_url, sarif, user)
                except Exception as msg:
                    logger.error("Unable to import %s: %s", blob.name, msg)
                    continue

    def filename_to_package_url(self, filename):
        """Convert a filename to a PackageURL."""
        print(filename)
        match = re.match(
            r"^(?P<type>[^/]+)/(?P<namespace>[^/]+)/(?P<name>[^/]+)/(?P<version>[^/]+)/.*$",
            filename,
        )
        if not match:
            match = re.match(r"^(?P<type>[^/]+)/(?P<name>[^/]+)/(?P<version>[^/]+)/.*$", filename)
        if not match:
            logger.debug("Unable to parse filename [%s]", filename)
            return None

        try:
            return PackageURL(
                match.group("type"),
                match.group("namespace") if "namespace" in match.groups() else None,
                match.group("name"),
                match.group("version"),
            )
        except Exception as msg:
            logger.debug("Unable to create PackageURL from %s: %s", filename, msg)
            return None

    def initialize_toolshed(self):
        if not TOOLSHED_BLOB_STORAGE_URL_SECRET or not TOOLSHED_BLOB_STORAGE_CONTAINER_SECRET:
            raise ValueError("TOOLSHED_BLOB_STORAGE_URL and TOOLSHED_BLOB_CONTAINER must be set")

        self.blob_service = BlobServiceClient(TOOLSHED_BLOB_STORAGE_URL_SECRET)

        self.container = self.blob_service.get_container_client(
            TOOLSHED_BLOB_STORAGE_CONTAINER_SECRET
        )
