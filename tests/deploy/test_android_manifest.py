from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ANDROID_NS = "http://schemas.android.com/apk/res/android"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "mobile-app/android/app/src/main/AndroidManifest.xml"


def test_release_manifest_allows_backend_network_requests() -> None:
    root = ET.parse(MANIFEST).getroot()
    permissions = {
        item.attrib.get(f"{{{ANDROID_NS}}}name")
        for item in root.findall("uses-permission")
    }
    application = root.find("application")

    assert "android.permission.INTERNET" in permissions
    assert application is not None
    assert application.attrib.get(f"{{{ANDROID_NS}}}usesCleartextTraffic") == "true"


def test_release_manifest_declares_android_location_permissions() -> None:
    root = ET.parse(MANIFEST).getroot()
    permissions = {
        item.attrib.get(f"{{{ANDROID_NS}}}name")
        for item in root.findall("uses-permission")
    }

    assert "android.permission.ACCESS_COARSE_LOCATION" in permissions
    assert "android.permission.ACCESS_FINE_LOCATION" in permissions
