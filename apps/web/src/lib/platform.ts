/**
 * Extended Navigator interface for User-Agent Client Hints API.
 * https://developer.mozilla.org/en-US/docs/Web/API/Navigator/userAgentData
 */
interface NavigatorUAData {
  platform?: string;
}

interface NavigatorWithUAData extends Navigator {
  userAgentData?: NavigatorUAData;
}

/**
 * Detects if the current platform is macOS.
 * Safe for SSR - returns false when window/navigator is unavailable.
 */
export function getIsMacOS(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined") {
    return false;
  }

  const nav = navigator as NavigatorWithUAData;

  // Modern API (Chrome 90+, Edge 90+)
  if (nav.userAgentData?.platform) {
    return nav.userAgentData.platform.toLowerCase().includes("mac");
  }

  // Fallback to navigator.platform (deprecated but widely supported)
  if (navigator.platform) {
    return navigator.platform.toLowerCase().includes("mac");
  }

  // Final fallback: check userAgent string
  return navigator.userAgent.toLowerCase().includes("macintosh");
}
