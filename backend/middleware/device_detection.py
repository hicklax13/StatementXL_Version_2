"""
Device detection middleware.

Provides device type detection and responsive content delivery.
"""
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class DeviceType(str, Enum):
    """Device type classifications."""
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    BOT = "bot"
    UNKNOWN = "unknown"


class BrowserType(str, Enum):
    """Browser type classifications."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"
    IE = "ie"
    OPERA = "opera"
    SAMSUNG = "samsung"
    OTHER = "other"


class OSType(str, Enum):
    """Operating system classifications."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    IOS = "ios"
    ANDROID = "android"
    OTHER = "other"


@dataclass
class DeviceInfo:
    """Parsed device information."""
    device_type: DeviceType
    browser: BrowserType
    os: OSType
    is_mobile: bool
    is_tablet: bool
    is_desktop: bool
    is_bot: bool
    user_agent: str
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    pixel_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_type": self.device_type.value,
            "browser": self.browser.value,
            "os": self.os.value,
            "is_mobile": self.is_mobile,
            "is_tablet": self.is_tablet,
            "is_desktop": self.is_desktop,
            "is_bot": self.is_bot,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "pixel_ratio": self.pixel_ratio,
        }


# Regex patterns for device detection
MOBILE_PATTERNS = [
    r"Mobile", r"Android.*Mobile", r"iPhone", r"iPod",
    r"BlackBerry", r"IEMobile", r"Opera Mini", r"Opera Mobi",
    r"Windows Phone", r"webOS", r"Palm", r"Symbian",
]

TABLET_PATTERNS = [
    r"iPad", r"Android(?!.*Mobile)", r"Tablet",
    r"PlayBook", r"Kindle", r"Silk",
]

BOT_PATTERNS = [
    r"bot", r"crawl", r"spider", r"slurp", r"search",
    r"Googlebot", r"Bingbot", r"Baiduspider", r"DuckDuckBot",
    r"YandexBot", r"facebookexternalhit", r"Twitterbot",
]

BROWSER_PATTERNS = {
    BrowserType.CHROME: r"Chrome/[\d.]+",
    BrowserType.FIREFOX: r"Firefox/[\d.]+",
    BrowserType.SAFARI: r"Safari/[\d.]+(?!.*Chrome)",
    BrowserType.EDGE: r"Edg/[\d.]+",
    BrowserType.IE: r"MSIE|Trident",
    BrowserType.OPERA: r"OPR/[\d.]+|Opera",
    BrowserType.SAMSUNG: r"SamsungBrowser",
}

OS_PATTERNS = {
    OSType.WINDOWS: r"Windows NT",
    OSType.MACOS: r"Mac OS X",
    OSType.LINUX: r"Linux(?!.*Android)",
    OSType.IOS: r"iPhone|iPad|iPod",
    OSType.ANDROID: r"Android",
}


def parse_user_agent(user_agent: str) -> DeviceInfo:
    """
    Parse user agent string to extract device information.

    Args:
        user_agent: User-Agent header string

    Returns:
        DeviceInfo with parsed details
    """
    if not user_agent:
        return DeviceInfo(
            device_type=DeviceType.UNKNOWN,
            browser=BrowserType.OTHER,
            os=OSType.OTHER,
            is_mobile=False,
            is_tablet=False,
            is_desktop=True,
            is_bot=False,
            user_agent="",
        )

    ua_lower = user_agent.lower()

    # Detect bot
    is_bot = any(re.search(pattern, ua_lower) for pattern in BOT_PATTERNS)

    # Detect device type
    is_mobile = any(re.search(pattern, user_agent, re.I) for pattern in MOBILE_PATTERNS)
    is_tablet = any(re.search(pattern, user_agent, re.I) for pattern in TABLET_PATTERNS)
    is_desktop = not is_mobile and not is_tablet and not is_bot

    if is_bot:
        device_type = DeviceType.BOT
    elif is_tablet:
        device_type = DeviceType.TABLET
    elif is_mobile:
        device_type = DeviceType.MOBILE
    else:
        device_type = DeviceType.DESKTOP

    # Detect browser
    browser = BrowserType.OTHER
    for browser_type, pattern in BROWSER_PATTERNS.items():
        if re.search(pattern, user_agent, re.I):
            browser = browser_type
            break

    # Detect OS
    os_type = OSType.OTHER
    for os_enum, pattern in OS_PATTERNS.items():
        if re.search(pattern, user_agent, re.I):
            os_type = os_enum
            break

    return DeviceInfo(
        device_type=device_type,
        browser=browser,
        os=os_type,
        is_mobile=is_mobile,
        is_tablet=is_tablet,
        is_desktop=is_desktop,
        is_bot=is_bot,
        user_agent=user_agent,
    )


def parse_client_hints(request: Request, device_info: DeviceInfo) -> DeviceInfo:
    """
    Enhance device info with Client Hints if available.

    Args:
        request: FastAPI request object
        device_info: Basic device info from user agent

    Returns:
        Enhanced DeviceInfo
    """
    # Parse Sec-CH-UA-Mobile
    mobile_hint = request.headers.get("Sec-CH-UA-Mobile")
    if mobile_hint:
        device_info.is_mobile = mobile_hint == "?1"

    # Parse Sec-CH-UA-Platform
    platform_hint = request.headers.get("Sec-CH-UA-Platform")
    if platform_hint:
        platform = platform_hint.strip('"').lower()
        if platform == "android":
            device_info.os = OSType.ANDROID
        elif platform == "ios":
            device_info.os = OSType.IOS
        elif platform == "windows":
            device_info.os = OSType.WINDOWS
        elif platform in ("macos", "mac os"):
            device_info.os = OSType.MACOS
        elif platform == "linux":
            device_info.os = OSType.LINUX

    # Parse viewport dimensions if provided
    viewport_width = request.headers.get("Viewport-Width")
    if viewport_width:
        try:
            device_info.screen_width = int(viewport_width)
        except ValueError:
            pass

    dpr = request.headers.get("DPR")
    if dpr:
        try:
            device_info.pixel_ratio = float(dpr)
        except ValueError:
            pass

    return device_info


class DeviceDetectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that detects device type and adds info to request state.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and add device info."""
        user_agent = request.headers.get("User-Agent", "")

        # Parse user agent
        device_info = parse_user_agent(user_agent)

        # Enhance with client hints
        device_info = parse_client_hints(request, device_info)

        # Add to request state
        request.state.device_info = device_info

        # Add header for downstream services
        response = await call_next(request)
        response.headers["X-Device-Type"] = device_info.device_type.value

        return response


def get_device_info(request: Request) -> DeviceInfo:
    """
    Get device info from request state.

    Args:
        request: FastAPI request object

    Returns:
        DeviceInfo from request state or parsed from headers
    """
    if hasattr(request.state, "device_info"):
        return request.state.device_info

    user_agent = request.headers.get("User-Agent", "")
    device_info = parse_user_agent(user_agent)
    return parse_client_hints(request, device_info)


# Responsive image utilities
def get_responsive_image_url(
    base_url: str,
    device_info: DeviceInfo,
    widths: Dict[DeviceType, int] = None,
) -> str:
    """
    Get responsive image URL based on device type.

    Args:
        base_url: Base image URL
        device_info: Device information
        widths: Optional width mapping per device type

    Returns:
        URL with appropriate size parameters
    """
    default_widths = {
        DeviceType.MOBILE: 480,
        DeviceType.TABLET: 768,
        DeviceType.DESKTOP: 1200,
    }

    widths = widths or default_widths
    width = widths.get(device_info.device_type, 1200)

    # Apply pixel ratio if available
    if device_info.pixel_ratio and device_info.pixel_ratio > 1:
        width = int(width * min(device_info.pixel_ratio, 3))

    # Add width parameter to URL
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}w={width}"


# Pagination utilities for different devices
def get_page_size(device_info: DeviceInfo, default: int = 20) -> int:
    """
    Get appropriate page size based on device type.

    Args:
        device_info: Device information
        default: Default page size

    Returns:
        Appropriate page size for device
    """
    page_sizes = {
        DeviceType.MOBILE: 10,
        DeviceType.TABLET: 15,
        DeviceType.DESKTOP: 20,
    }

    return page_sizes.get(device_info.device_type, default)


# Content adaptation utilities
def should_lazy_load(device_info: DeviceInfo) -> bool:
    """Check if content should be lazy loaded for device."""
    return device_info.is_mobile or device_info.is_tablet


def get_thumbnail_size(device_info: DeviceInfo) -> tuple:
    """Get appropriate thumbnail size for device."""
    sizes = {
        DeviceType.MOBILE: (150, 150),
        DeviceType.TABLET: (200, 200),
        DeviceType.DESKTOP: (300, 300),
    }
    return sizes.get(device_info.device_type, (200, 200))
