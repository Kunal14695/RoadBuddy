/**
 * RoadBuddy — Auto-Reroute Navigation Module
 * --------------------------------------------
 * Handles GPS deviation detection, route recalculation via Mapbox Directions API,
 * and seamless HUD / map line updates without interrupting active navigation mode.
 */

(function (window) {
  const REROUTE_THRESHOLD_METERS = 50;
  const REROUTE_COOLDOWN_MS = 8000;
  const MIN_CONSECUTIVE_OFFROUTE_READS = 3;
  const MIN_GPS_ACCURACY_METERS = 30;

  let offRouteStreak = 0;
  let lastRerouteAt = 0;
  let toastTimer = null;

  // Calculate distance between two lat/lon points in kilometers
  function getDistanceKm(lat1, lon1, lat2, lon2) {
    if (!lat1 || !lon1 || !lat2 || !lon2) return 0;
    const R = 6371.0;
    const dLat = (lat2 - lat1) * (Math.PI / 180);
    const dLon = (lon2 - lon1) * (Math.PI / 180);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * (Math.PI / 180)) *
        Math.cos(lat2 * (Math.PI / 180)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  // Distance from point (pLat, pLon) to line segment (aLat, aLon) -> (bLat, bLon) in km
  function distanceToSegmentKm(pLat, pLon, aLat, aLon, bLat, bLon) {
    const l2 = Math.pow(bLat - aLat, 2) + Math.pow(bLon - aLon, 2);
    if (l2 === 0) return getDistanceKm(pLat, pLon, aLat, aLon);
    let t = ((pLat - aLat) * (bLat - aLat) + (pLon - aLon) * (bLon - aLon)) / l2;
    t = Math.max(0, Math.min(1, t));
    const projLat = aLat + t * (bLat - aLat);
    const projLon = aLon + t * (bLon - aLon);
    return getDistanceKm(pLat, pLon, projLat, projLon);
  }

  // Get minimum perpendicular distance from user location to polyline in meters
  function getDistanceFromRoute(userLat, userLon, polyline) {
    if (!polyline || polyline.length === 0) return 0;
    let minDistKm = Infinity;
    const step = polyline.length > 300 ? Math.ceil(polyline.length / 150) : 1;

    for (let i = 0; i < polyline.length - step; i += step) {
      const ptA = polyline[i];
      const ptB = polyline[i + step];
      const aLat = ptA.lat,
        aLon = ptA.lng != null ? ptA.lng : ptA.lon;
      const bLat = ptB.lat,
        bLon = ptB.lng != null ? ptB.lng : ptB.lon;

      const dist = distanceToSegmentKm(userLat, userLon, aLat, aLon, bLat, bLon);
      if (dist < minDistKm) minDistKm = dist;
    }
    return minDistKm * 1000.0; // convert km to meters
  }

  // Filter out waypoints that user has already passed along route
  function getUnvisitedWaypoints(userLat, userLon, waypoints, polyline) {
    if (!waypoints || waypoints.length === 0) return [];
    if (!polyline || polyline.length === 0) return waypoints;

    // Find nearest segment index on polyline for current user location
    let closestIndex = 0;
    let minDist = Infinity;
    for (let i = 0; i < polyline.length; i++) {
      const pt = polyline[i];
      const lat = pt.lat,
        lon = pt.lng != null ? pt.lng : pt.lon;
      const d = getDistanceKm(userLat, userLon, lat, lon);
      if (d < minDist) {
        minDist = d;
        closestIndex = i;
      }
    }

    // Keep waypoints whose closest polyline point index is >= user's current index
    return waypoints.filter((wp) => {
      let wpClosestIndex = 0;
      let wpMinDist = Infinity;
      for (let i = 0; i < polyline.length; i++) {
        const pt = polyline[i];
        const lat = pt.lat,
          lon = pt.lng != null ? pt.lng : pt.lon;
        const d = getDistanceKm(wp.lat, wp.lon, lat, lon);
        if (d < wpMinDist) {
          wpMinDist = d;
          wpClosestIndex = i;
        }
      }
      return wpClosestIndex >= closestIndex - 3;
    });
  }

  // Display unobtrusive toast message
  function showRerouteToast(message, isError = false) {
    let el = document.getElementById("reroute-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "reroute-toast";
      el.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.92);
        color: #ffffff;
        font-size: 13px;
        font-weight: 700;
        padding: 8px 18px;
        border-radius: 20px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: all 0.3s ease;
        backdrop-filter: blur(6px);
      `;
      document.body.appendChild(el);
    }
    el.style.background = isError ? "rgba(225, 29, 72, 0.92)" : "rgba(15, 23, 42, 0.92)";
    el.innerHTML = `<span class="material-symbols-outlined" style="font-size: 16px;">${
      isError ? "error_outline" : "alt_route"
    }</span> ${message}`;
    el.style.opacity = "1";
    el.style.transform = "translateX(-50%) translateY(0)";

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      hideRerouteToast();
    }, 4000);
  }

  function hideRerouteToast() {
    const el = document.getElementById("reroute-toast");
    if (el) {
      el.style.opacity = "0";
      el.style.transform = "translateX(-50%) translateY(10px)";
    }
  }

  // Check if user has deviated from active route
  function checkForReroute(userLat, userLon, gpsAccuracy) {
    if (!window.isNavigating || !window.currentPolyline) return;
    if (gpsAccuracy && gpsAccuracy > MIN_GPS_ACCURACY_METERS) return;

    const distFromRoute = getDistanceFromRoute(userLat, userLon, window.currentPolyline);

    if (distFromRoute > REROUTE_THRESHOLD_METERS) {
      offRouteStreak++;
    } else {
      offRouteStreak = 0;
      return;
    }

    if (offRouteStreak < MIN_CONSECUTIVE_OFFROUTE_READS) return;

    const now = Date.now();
    if (now - lastRerouteAt < REROUTE_COOLDOWN_MS) return;

    lastRerouteAt = now;
    offRouteStreak = 0;
    triggerReroute(userLat, userLon);
  }

  // Recalculate route from current position to destination
  async function triggerReroute(userLat, userLon) {
    showRerouteToast("Recalculating route...");

    if (typeof window.fetchRerouteFromPosition === "function") {
      try {
        const success = await window.fetchRerouteFromPosition(userLat, userLon);
        if (success) {
          showRerouteToast("Route updated");
        } else {
          showRerouteToast("Couldn't reroute — check connection", true);
        }
      } catch (e) {
        showRerouteToast("Reroute failed", true);
      }
    }
  }

  // Export module functions globally
  window.RoadBuddyNav = {
    getDistanceKm,
    distanceToSegmentKm,
    getDistanceFromRoute,
    getUnvisitedWaypoints,
    checkForReroute,
    triggerReroute,
    showRerouteToast,
    hideRerouteToast,
  };
})(window);
