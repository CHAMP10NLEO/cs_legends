(function () {
  "use strict";

  var dataNode = document.getElementById("map-events");
  var globeNode = document.getElementById("globe");
  var fallback = document.getElementById("map-fallback");
  var panel = document.getElementById("event-detail");
  var panelContent = document.getElementById("event-detail-content");
  var closeButton = document.getElementById("event-detail-close");
  if (!dataNode || !globeNode) return;

  var events = [];
  try {
    events = JSON.parse(dataNode.textContent || "[]");
  } catch (error) {
    return;
  }

  var COUNTRY_ALIAS = {
    "阿联酋": "阿拉伯联合酋长国"
  };

  // 版本号用于打破浏览器对旧国界数据的强缓存。
  var COUNTRIES_URL = "/static/data/countries.geojson?v=20261120";
  // 半透明面让底下的夜景纹理透出来，避免整块实色显得扁平。
  var CAP_IDLE = "rgba(28, 48, 66, 0.72)";
  var CAP_HOST = "rgba(44, 84, 106, 0.9)";
  var CAP_HOVER = "rgba(74, 222, 128, 0.34)";
  // 侧面贴近面颜色，避免海岸线出现一圈发黑的"阴影带"。
  var SIDE_IDLE = "rgba(20, 38, 54, 0.7)";
  var SIDE_HOVER = "rgba(74, 222, 128, 0.36)";
  var STROKE_IDLE = "rgba(94, 234, 212, 0.14)";
  var STROKE_HOST = "rgba(94, 234, 212, 0.38)";
  var STROKE_HOVER = "rgba(167, 243, 208, 0.95)";

  var ORGANIZER_META = {
    "ESL": { short: "ESL", color: "#4f9cf9" },
    "BLAST": { short: "BLAST", color: "#f5c451" },
    "PGL": { short: "PGL", color: "#f472b6" },
    "StarLadder": { short: "SL", color: "#f87171" },
    "Beyond the Summit": { short: "BTS", color: "#34d399" },
    "FACEIT": { short: "FACEIT", color: "#fb923c" },
    "Epic Esports Events": { short: "EPIC", color: "#a78bfa" },
    "Gamers8 (Saudi Esports Federation)": { short: "G8", color: "#2dd4bf" }
  };

  var globe = null;
  var hoveredCountry = null;
  var pinnedCountry = null;
  var eventsByCountry = {};
  var markers = [];
  var resumeTimer = null;
  var markerTimer = null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function countryKey(name) {
    return COUNTRY_ALIAS[name] || name;
  }

  function groupEventsByCountry() {
    events.forEach(function (event) {
      if (!event.organizer) return;
      var name = countryKey(event.country || "");
      if (!name) return;
      if (!eventsByCountry[name]) eventsByCountry[name] = [];
      eventsByCountry[name].push(event);
    });
  }

  function organizerMeta(name) {
    return ORGANIZER_META[name] || { short: String(name).slice(0, 4).toUpperCase(), color: "#94a3b8" };
  }

  // 每个国家一枚标记，归集该国的赛事数与主办方，位置取最近一届赛事的城市。
  function buildMarkers() {
    var byCountry = {};

    events.forEach(function (event) {
      if (!event.organizer) return;
      if (typeof event.lat !== "number" || typeof event.lng !== "number") return;
      var key = countryKey(event.country || "");
      if (!key) return;
      var entry = byCountry[key];
      if (!entry) {
        entry = byCountry[key] = { label: event.country, lat: event.lat, lng: event.lng, total: 0, orgs: {} };
      }
      entry.lat = event.lat;
      entry.lng = event.lng;
      entry.total += 1;
      entry.lastOrg = event.organizer;
      entry.orgs[event.organizer] = (entry.orgs[event.organizer] || 0) + 1;
    });

    markers = Object.keys(byCountry).map(function (key) {
      var entry = byCountry[key];
      var orgs = Object.keys(entry.orgs)
        .map(function (name) {
          var meta = organizerMeta(name);
          return { name: name, short: meta.short, color: meta.color, count: entry.orgs[name] };
        })
        .sort(function (a, b) {
          return b.count - a.count || (b.name === entry.lastOrg) - (a.name === entry.lastOrg);
        });

      return {
        label: entry.label,
        lat: entry.lat,
        lng: entry.lng,
        total: entry.total,
        orgs: orgs,
        el: null
      };
    });
  }

  function markerElement(marker) {
    var el = document.createElement("div");
    el.className = "map-marker";
    el.dataset.country = marker.label;
    if (marker.orgs.length) {
      el.style.setProperty("--dot", marker.orgs[0].color);
    }
    el.title =
      marker.label +
      " · " +
      marker.total +
      " 届赛事 · " +
      marker.orgs
        .map(function (org) {
          return org.name + (org.count > 1 ? " x" + org.count : "");
        })
        .join(" / ");

    marker.orgs.forEach(function (org) {
      var badge = document.createElement("span");
      badge.className = "map-marker__badge";
      badge.style.setProperty("--badge", org.color);
      badge.textContent = org.short;

      if (org.count > 1) {
        var count = document.createElement("i");
        count.className = "map-marker__count";
        count.textContent = org.count;
        badge.appendChild(count);
      }

      el.appendChild(badge);
    });

    marker.el = el;
    return el;
  }

  // 背面裁剪 + 屏幕空间去重叠：背面与过度重叠的标记暂时隐藏，放大后自然分开。
  function updateMarkerVisibility() {
    if (!globe || !markers.length) return;

    var camera = globe.camera().position;
    var cameraLength = Math.sqrt(
      camera.x * camera.x + camera.y * camera.y + camera.z * camera.z
    );
    var radius;
    try {
      radius = globe.globeRadius();
    } catch (error) {
      radius = 100;
    }
    var horizon = radius * radius;
    var placed = [];

    markers
      .slice()
      .sort(function (a, b) {
        return b.total - a.total;
      })
      .forEach(function (marker) {
        var el = marker.el;
        if (!el) return;

        var coords;
        try {
          coords = globe.getCoords(marker.lat, marker.lng, 0.012);
        } catch (error) {
          return;
        }
        if (!coords) return;

        // 球面点与相机连线夹角超过地平线时，标记在地球背面。
        var facing = coords.x * camera.x + coords.y * camera.y + coords.z * camera.z;
        if (cameraLength > 0 && facing < horizon) {
          el.classList.add("is-hidden");
          return;
        }
        el.classList.remove("is-hidden");

        var width = el.offsetWidth;
        var height = el.offsetHeight;
        if (!width || !height) return;

        var point;
        try {
          point = globe.getScreenCoords(marker.lat, marker.lng, 0.012);
        } catch (error) {
          return;
        }
        if (!point) return;

        var clash = placed.some(function (box) {
          return (
            Math.abs(point.x - box.x) < (width + box.w) / 2 + 2 &&
            Math.abs(point.y - box.y) < (height + box.h) / 2 + 2
          );
        });

        el.classList.toggle("is-collided", clash);
        if (!clash) {
          placed.push({ x: point.x, y: point.y, w: width, h: height });
        }
      });
  }

  function scheduleMarkerUpdate() {
    if (markerTimer) return;
    markerTimer = window.setTimeout(function () {
      markerTimer = null;
      updateMarkerVisibility();
    }, 140);
  }

  function resultClass(event) {
    var tags = event.tags || [];
    if (tags.indexOf("champion") !== -1) return "is-win";
    if (tags.indexOf("major") !== -1) return "is-major";
    return "is-muted";
  }

  function matchesHtml(event) {
    var matches = event.matches || [];
    if (!matches.length) return "";

    var wins = matches.filter(function (match) {
      return match.result === "胜";
    }).length;

    var hasStage = matches.some(function (match) {
      return match.stage;
    });

    var rows = matches
      .map(function (match) {
        var win = match.result === "胜";
        return (
          "<li>" +
          (hasStage ? '<span class="match-stage">' + escapeHtml(match.stage) + "</span>" : "") +
          '<span class="match-opponent">' + escapeHtml(match.opponent) + "</span>" +
          '<span class="match-score">' + escapeHtml(match.score) + "</span>" +
          '<span class="match-result ' + (win ? "is-win" : "is-loss") + '">' +
          escapeHtml(match.result) +
          "</span>" +
          "</li>"
        );
      })
      .join("");

    return (
      '<div class="detail-matches__head">' +
      "<h3>本届全部比赛</h3>" +
      "<span>" +
      matches.length +
      " 场 · " +
      wins +
      " 胜 " +
      (matches.length - wins) +
      " 负</span>" +
      "</div>" +
      '<ol class="match-list' +
      (hasStage ? "" : " match-list--plain") +
      '">' +
      rows +
      "</ol>"
    );
  }

  function eventBlockHtml(event) {
    var place = [event.city, event.country].filter(Boolean).join(" · ");
    var organizer = event.organizer || "未记录";
    var venue = event.venue || (event.city === "线上" ? "线上赛" : "未记录");

    return (
      '<article class="country-event">' +
      '<p class="detail-date">' +
      escapeHtml(event.date_label) +
      " · " +
      escapeHtml(place) +
      "</p>" +
      '<h3 class="country-event__title">' +
      escapeHtml(event.title) +
      "</h3>" +
      '<p class="detail-result ' +
      resultClass(event) +
      '">' +
      escapeHtml(event.result) +
      "</p>" +
      '<dl class="detail-meta">' +
      "<div><dt>主办方</dt><dd>" +
      escapeHtml(organizer) +
      "</dd></div>" +
      "<div><dt>场馆</dt><dd>" +
      escapeHtml(venue) +
      "</dd></div>" +
      "</dl>" +
      '<p class="detail-summary">' +
      escapeHtml(event.summary) +
      "</p>" +
      matchesHtml(event) +
      "</article>"
    );
  }

  function countryHtml(feature) {
    var props = feature.properties || {};
    var name = props.NAME_ZH || props.NAME || "未知地区";
    var list = eventsByCountry[countryKey(name)] || [];
    var matchCount = list.reduce(function (total, event) {
      return total + (event.matches ? event.matches.length : 0);
    }, 0);

    var body;
    if (!list.length) {
      body = '<p class="detail-empty">ZywOo 暂无在该国的赛事记录。</p>';
    } else {
      body =
        '<p class="country-stats">' +
        list.length +
        " 届赛事 · " +
        matchCount +
        " 场比赛</p>" +
        '<div class="country-events">' +
        list.map(eventBlockHtml).join("") +
        "</div>";
    }

    return (
      '<p class="eyebrow">国家 / 地区</p>' +
      "<h2>" +
      escapeHtml(name) +
      "</h2>" +
      body
    );
  }

  function pauseRotation() {
    if (resumeTimer) {
      window.clearTimeout(resumeTimer);
      resumeTimer = null;
    }
    if (globe) globe.controls().autoRotate = false;
  }

  function scheduleRotation() {
    if (!globe) return;
    if (resumeTimer) window.clearTimeout(resumeTimer);
    resumeTimer = window.setTimeout(function () {
      if (panel && !panel.hidden) return;
      globe.controls().autoRotate = true;
    }, 4000);
  }

  function showCountry(feature) {
    if (!panel || !panelContent || !feature) return;
    panelContent.innerHTML = countryHtml(feature);
    panel.hidden = false;
    panel.scrollTop = 0;
    pauseRotation();
  }

  function hideDetail() {
    if (!panel) return;
    pinnedCountry = null;
    panel.hidden = true;
    scheduleRotation();
  }

  if (closeButton) {
    closeButton.addEventListener("click", hideDetail);
  }

  function showFallback(message) {
    if (!fallback) return;
    fallback.textContent = message;
    fallback.hidden = false;
  }

  function polygonAltitude(feature) {
    return feature === hoveredCountry ? 0.018 : 0.004;
  }

  function hasEvents(feature) {
    var props = feature.properties || {};
    var name = countryKey(props.NAME_ZH || props.NAME || "");
    return !!(eventsByCountry[name] && eventsByCountry[name].length);
  }

  function polygonCapColor(feature) {
    if (feature === hoveredCountry) return CAP_HOVER;
    return hasEvents(feature) ? CAP_HOST : CAP_IDLE;
  }

  function polygonSideColor(feature) {
    return feature === hoveredCountry ? SIDE_HOVER : SIDE_IDLE;
  }

  function polygonStrokeColor(feature) {
    if (feature === hoveredCountry) return STROKE_HOVER;
    return hasEvents(feature) ? STROKE_HOST : STROKE_IDLE;
  }

  function refreshPolygons() {
    globe
      .polygonAltitude(polygonAltitude)
      .polygonCapColor(polygonCapColor)
      .polygonSideColor(polygonSideColor)
      .polygonStrokeColor(polygonStrokeColor);
  }

  // 提高海洋高光，并补一盏冷色轮廓光，让球体边缘更有体积感。
  function refineMaterial() {
    if (!globe) return;

    var material = globe.globeMaterial();
    if (material) {
      material.shininess = 8;
      if (material.specular && material.specular.setStyle) {
        material.specular.setStyle("#24384a");
      }
    }

    var lights = globe.lights() || [];
    var template = null;
    lights.forEach(function (light) {
      if (light.isAmbientLight) light.intensity = 3.8;
      if (light.isDirectionalLight) {
        light.intensity = 2.2;
        if (!template) template = light;
      }
    });
    if (!template || !template.clone) return;

    var rim = template.clone();
    rim.position.set(-100, -45, -80);
    if (rim.color && rim.color.setStyle) rim.color.setStyle("#5eead4");
    rim.intensity = 0.5;
    globe.scene().add(rim);
  }

  function initGlobe(countries) {
    if (typeof window.Globe === "undefined") {
      showFallback("3D 地球加载失败，请检查网络后刷新。");
      return;
    }

    var narrow = globeNode.clientWidth < 600;

    try {
      globe = window.Globe()(globeNode);
    } catch (error) {
      showFallback("当前浏览器不支持 WebGL，无法渲染 3D 地球。");
      return;
    }

    globe
      .backgroundColor("rgba(0,0,0,0)")
      .globeImageUrl("/static/images/globe/earth-night.jpg")
      .bumpImageUrl("/static/images/globe/earth-topology.png")
      .showAtmosphere(true)
      .atmosphereColor("#5eead4")
      .atmosphereAltitude(0.13)
      .polygonsData(countries)
      .polygonAltitude(polygonAltitude)
      .polygonCapColor(polygonCapColor)
      .polygonSideColor(polygonSideColor)
      .polygonStrokeColor(polygonStrokeColor)
      .polygonCapCurvatureResolution(3)
      .polygonsTransitionDuration(260)
      .htmlElementsData(markers)
      .htmlLat(function (marker) {
        return marker.lat;
      })
      .htmlLng(function (marker) {
        return marker.lng;
      })
      .htmlAltitude(0.012)
      .htmlElement(markerElement)
      .htmlTransitionDuration(0)
      .onPolygonHover(function (feature) {
        hoveredCountry = feature;
        refreshPolygons();
        globeNode.classList.toggle("is-over-country", !!feature && hasEvents(feature));
        // 已单击固定的国家面板不随悬停切换或关闭，直到被取消固定。
        if (feature) {
          if (!pinnedCountry) showCountry(feature);
        } else if (!pinnedCountry) {
          hideDetail();
        }
      })
      .onPolygonClick(function (feature) {
        if (!feature) return;
        pinnedCountry = feature;
        showCountry(feature);
      })
      .onGlobeClick(hideDetail);

    refineMaterial();

    globe.pointOfView(
      { lat: 24, lng: 18, altitude: narrow ? 2.6 : 2.0 },
      0
    );

    var controls = globe.controls();
    controls.enableZoom = true;
    controls.enablePan = false;
    controls.minDistance = 120;
    controls.maxDistance = 480;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.32;

    controls.addEventListener("start", pauseRotation);
    controls.addEventListener("end", function () {
      if (!hoveredCountry) scheduleRotation();
    });
    controls.addEventListener("change", scheduleMarkerUpdate);

    window.setInterval(updateMarkerVisibility, 400);
    updateMarkerVisibility();

    // 等首帧画出来再淡入画布，避免纹理加载前的空球闪一下。
    window.requestAnimationFrame(function () {
      globeNode.classList.add("is-ready");
    });

    window.addEventListener("resize", function () {
      if (globe) globe.width(globeNode.clientWidth).height(globeNode.clientHeight);
      scheduleMarkerUpdate();
    });
  }

  function loadCountries() {
    fetch(COUNTRIES_URL)
      .then(function (response) {
        if (!response.ok) throw new Error("countries " + response.status);
        return response.json();
      })
      .then(function (geojson) {
        initGlobe(geojson.features || []);
      })
      .catch(function () {
        showFallback("国家边界数据加载失败，请刷新重试。");
      });
  }

  var picker = document.querySelector(".player-picker");
  var toggle = document.getElementById("player-toggle");
  var menu = document.getElementById("player-menu");
  if (picker && toggle && menu) {
    var setMenu = function (open) {
      menu.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };

    toggle.addEventListener("click", function (event) {
      event.stopPropagation();
      setMenu(menu.hidden);
    });

    menu.addEventListener("click", function (event) {
      var option = event.target.closest("[data-player]");
      if (option) setMenu(false);
    });

    document.addEventListener("click", function (event) {
      if (!picker.contains(event.target)) setMenu(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        setMenu(false);
        hideDetail();
        hoveredCountry = null;
        if (globe) refreshPolygons();
      }
    });
  }

  groupEventsByCountry();
  buildMarkers();
  loadCountries();
})();
