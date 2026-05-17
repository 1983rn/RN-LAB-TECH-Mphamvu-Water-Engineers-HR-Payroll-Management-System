/**
 * Leaflet GPS maps: satellite/OSM, HD zoom, capture with coordinates, load toast.
 */
(function (global) {
    'use strict';

    var DEFAULT_CENTER = [-13.9626, 33.7741];
    var DEFAULT_ZOOM = 7;
    var DETAIL_ZOOM = 18;
    var HD_ZOOM = 20;
    var MIN_ZOOM = 2;
    var MAX_ZOOM = 22;
    var MAX_NATIVE_ZOOM = 19;

    var SATELLITE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    var SATELLITE_ATTRIBUTION = 'Tiles &copy; Esri';
    var OSM_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    var OSM_ATTRIBUTION = '&copy; OpenStreetMap contributors';

    var pendingFly = null;
    var captureBtnBusy = false;

    function parseCoord(value) {
        if (value === null || value === undefined || value === '') return null;
        var n = Number(value);
        return Number.isFinite(n) ? n : null;
    }

    function formatCoords(lat, lng) {
        return '(' + lat.toFixed(6) + ', ' + lng.toFixed(6) + ')';
    }

    function renderQuotationCoordsHint(lat, lng, clickable) {
        var hint = document.getElementById('project-location-coords-hint');
        if (!hint) return;

        if (lat === null || lng === null) {
            hint.textContent = 'Not set — open the GPS tab to place a pin, then click Load on quotation.';
            return;
        }

        var label = formatCoords(lat, lng);
        if (clickable) {
            hint.innerHTML = '<button type="button" class="btn btn-link btn-sm p-0 align-baseline quotation-gps-coords-link text-primary" '
                + 'data-lat="' + lat + '" data-lng="' + lng + '" title="Show this location on the map">'
                + label + ' <i class="fas fa-map-marker-alt small" aria-hidden="true"></i></button>';
        } else {
            hint.textContent = label;
        }
    }

    function showGpsToast(message, variant) {
        variant = variant || 'success';
        var bgClass = variant === 'danger' ? 'text-bg-danger'
            : variant === 'warning' ? 'text-bg-warning'
                : variant === 'info' ? 'text-bg-info' : 'text-bg-success';

        var container = document.getElementById('quotation-gps-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'quotation-gps-toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '2000';
            document.body.appendChild(container);
        }

        var toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center border-0 ' + bgClass;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = '<div class="d-flex"><div class="toast-body">' + message
            + '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';

        container.appendChild(toastEl);

        if (global.bootstrap && bootstrap.Toast) {
            var toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 4500 });
            toastEl.addEventListener('hidden.bs.toast', function () {
                toastEl.remove();
            });
            toast.show();
        } else {
            alert(message.replace(/<[^>]+>/g, ' '));
            toastEl.remove();
        }
    }

    function isVisible(el) {
        if (!el || !el.offsetParent) {
            var pane = el && el.closest('.tab-pane');
            if (pane && pane.classList.contains('show')) return true;
            var modal = el && el.closest('.modal');
            if (modal && modal.classList.contains('show')) return true;
            if (pane || modal) return false;
        }
        return !!(el && (el.offsetWidth > 0 || el.offsetHeight > 0));
    }

    function whenReady(fn) {
        if (global.L) {
            fn();
            return;
        }
        var attempts = 0;
        function wait() {
            if (global.L) {
                fn();
                return;
            }
            attempts += 1;
            if (attempts > 100) {
                console.error('Leaflet failed to load for quotation GPS map.');
                return;
            }
            setTimeout(wait, 50);
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', wait);
        } else {
            wait();
        }
    }

    function tileOptions(extra) {
        var base = {
            maxZoom: MAX_ZOOM,
            maxNativeZoom: MAX_NATIVE_ZOOM,
            detectRetina: true,
            crossOrigin: 'anonymous'
        };
        if (extra) {
            Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
        }
        return base;
    }

    function createMap(mapEl, center, zoom) {
        var map = L.map(mapEl, {
            center: center,
            zoom: zoom,
            minZoom: MIN_ZOOM,
            maxZoom: MAX_ZOOM,
            zoomSnap: 0.25,
            zoomDelta: 0.5,
            zoomControl: true
        });

        var satellite = L.tileLayer(SATELLITE_URL, Object.assign({
            attribution: SATELLITE_ATTRIBUTION
        }, tileOptions()));
        var osm = L.tileLayer(OSM_URL, Object.assign({
            attribution: OSM_ATTRIBUTION
        }, tileOptions()));

        satellite.addTo(map);
        L.control.layers({
            'Satellite (HD)': satellite,
            'OpenStreetMap': osm
        }, null, { collapsed: true }).addTo(map);

        return { map: map, satellite: satellite, osm: osm };
    }

    function bindMapUi(ctx) {
        var mapWrap = ctx.mapWrap;
        var map = ctx.map;
        var hdBtn = ctx.hdButtonId ? document.getElementById(ctx.hdButtonId) : null;
        var captureBtn = ctx.captureButtonId ? document.getElementById(ctx.captureButtonId) : null;
        var captureLabel = ctx.captureLabelId ? document.getElementById(ctx.captureLabelId) : null;
        var hdOn = false;

        function setHdMode(enabled) {
            hdOn = enabled;
            if (mapWrap) {
                mapWrap.classList.toggle('quotation-gps-map--hd', enabled);
            }
            if (hdBtn) {
                hdBtn.classList.toggle('active', enabled);
                hdBtn.innerHTML = enabled
                    ? '<i class="fas fa-compress me-1"></i>Exit HD'
                    : '<i class="fas fa-expand me-1"></i>HD view';
            }
            setTimeout(function () {
                map.invalidateSize();
                if (enabled && ctx.getCoords) {
                    var c = ctx.getCoords();
                    if (c) {
                        map.setView([c.lat, c.lng], Math.min(HD_ZOOM, map.getMaxZoom()));
                    }
                }
            }, 120);
        }

        if (hdBtn) {
            hdBtn.addEventListener('click', function () {
                setHdMode(!hdOn);
                showGpsToast(hdOn ? 'HD view enabled — use +/− or scroll for fine detail (up to zoom ' + MAX_ZOOM + ').' : 'Standard map view restored.', 'info');
            });
        }

        if (captureBtn) {
            captureBtn.addEventListener('click', function () {
                var coords = ctx.getCoords ? ctx.getCoords() : null;
                if (!coords) {
                    showGpsToast('Place a pin on the map before capturing an image.', 'warning');
                    return;
                }
                captureMapImage(mapWrap, captureLabel, coords, map);
            });
        }

        ctx.setHdMode = setHdMode;
    }

    function getHtml2CanvasLib() {
        if (typeof global.html2canvas === 'function') {
            return global.html2canvas;
        }
        return null;
    }

    function buildCaptureLabel(coords, map) {
        return 'GPS: ' + formatCoords(coords.lat, coords.lng)
            + '  |  Zoom: ' + (map ? map.getZoom().toFixed(2) : '—')
            + '  |  ' + new Date().toLocaleString();
    }

    function drawCoordsBanner(ctx, w, h, label, scale) {
        var pad = 10 * scale;
        ctx.font = '600 ' + (13 * scale) + 'px system-ui, sans-serif';
        var textW = ctx.measureText(label).width;
        var boxH = 28 * scale;
        var boxW = Math.min(w - pad * 2, textW + pad * 2);
        var boxX = (w - boxW) / 2;
        var boxY = h - boxH - pad;
        ctx.fillStyle = 'rgba(0, 0, 0, 0.78)';
        ctx.fillRect(boxX, boxY, boxW, boxH);
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, w / 2, boxY + boxH / 2);
    }

    function captureWithLeafletTiles(map, mapWrap, coords) {
        var scale = Math.min(2, window.devicePixelRatio || 1.5);
        var rect = mapWrap.getBoundingClientRect();
        var w = Math.max(1, Math.round(rect.width * scale));
        var h = Math.max(1, Math.round(rect.height * scale));

        var canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#e9ecef';
        ctx.fillRect(0, 0, w, h);

        var tilesDrawn = 0;
        mapWrap.querySelectorAll('.leaflet-tile-pane img').forEach(function (img) {
            if (!img.complete || !img.naturalWidth) return;
            var r = img.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) return;
            
            var isCrossOrigin = false;
            try {
                isCrossOrigin = new URL(img.src).origin !== window.location.origin;
            } catch(e) {}
            if (isCrossOrigin && img.crossOrigin !== 'anonymous') return;

            try {
                ctx.drawImage(
                    img,
                    (r.left - rect.left) * scale,
                    (r.top - rect.top) * scale,
                    r.width * scale,
                    r.height * scale
                );
                tilesDrawn += 1;
            } catch (err) { /* cross-origin tile */ }
        });

        mapWrap.querySelectorAll('.leaflet-marker-pane img, .leaflet-shadow-pane img').forEach(function (img) {
            if (!img.complete || !img.naturalWidth) return;
            var r = img.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) return;
            
            var isCrossOrigin = false;
            try {
                isCrossOrigin = new URL(img.src).origin !== window.location.origin;
            } catch(e) {}
            
            if (isCrossOrigin && img.crossOrigin !== 'anonymous') {
                if (img.src.indexOf('shadow') !== -1) return;
                var cx = (r.left - rect.left + r.width / 2) * scale;
                var cy = (r.top - rect.top + r.height) * scale;
                ctx.beginPath();
                ctx.arc(cx, cy - 15 * scale, 10 * scale, 0, 2 * Math.PI);
                ctx.fillStyle = '#dc3545';
                ctx.fill();
                ctx.strokeStyle = 'white';
                ctx.lineWidth = 2 * scale;
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(cx - 10 * scale, cy - 15 * scale);
                ctx.lineTo(cx, cy);
                ctx.lineTo(cx + 10 * scale, cy - 15 * scale);
                ctx.fill();
                return;
            }

            try {
                ctx.drawImage(
                    img,
                    (r.left - rect.left) * scale,
                    (r.top - rect.top) * scale,
                    r.width * scale,
                    r.height * scale
                );
            } catch (err) { /* ignore */ }
        });

        drawCoordsBanner(ctx, w, h, buildCaptureLabel(coords, map), scale);
        
        try {
            canvas.toDataURL(); // Check if canvas got tainted
        } catch(e) {
            throw new Error('Canvas was tainted');
        }
        
        return { canvas: canvas, tilesDrawn: tilesDrawn };
    }

    function downloadCaptureCanvas(canvas, coords) {
        var fileName = 'project-satellite_' + coords.lat.toFixed(6) + '_' + coords.lng.toFixed(6) + '.png';
        var link = document.createElement('a');
        link.download = fileName;
        link.href = canvas.toDataURL('image/png');
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function captureWithHtml2Canvas(mapWrap, captureLabel, coords, map) {
        var h2c = getHtml2CanvasLib();
        if (!h2c) {
            return Promise.reject(new Error('html2canvas missing'));
        }

        if (captureLabel) {
            captureLabel.textContent = buildCaptureLabel(coords, map);
            captureLabel.classList.remove('d-none');
            captureLabel.setAttribute('aria-hidden', 'false');
        }

        return h2c(mapWrap, {
            useCORS: true,
            allowTaint: false,
            logging: false,
            scale: Math.min(2, window.devicePixelRatio || 1.5),
            backgroundColor: '#e9ecef',
            ignoreElements: function (el) {
                return el.classList && el.classList.contains('leaflet-control-container');
            }
        }).then(function (canvas) {
            if (captureLabel) {
                captureLabel.classList.add('d-none');
                captureLabel.setAttribute('aria-hidden', 'true');
            }
            return canvas;
        }).catch(function (err) {
            if (captureLabel) {
                captureLabel.classList.add('d-none');
                captureLabel.setAttribute('aria-hidden', 'true');
            }
            throw err;
        });
    }

    function captureMapImage(mapWrap, captureLabel, coords, map) {
        if (!mapWrap || !map) {
            showGpsToast('Map is not ready. Open the GPS tab and try again.', 'warning');
            return;
        }

        if (captureBtnBusy) return;
        captureBtnBusy = true;

        map.invalidateSize();
        map.whenReady(function () {
            setTimeout(function () {
                function done() {
                    captureBtnBusy = false;
                }

                function onSuccess(canvas, usedTiles) {
                    downloadCaptureCanvas(canvas, coords);
                    var msg = 'Satellite image saved with coordinates ' + formatCoords(coords.lat, coords.lng) + '.';
                    if (!usedTiles) {
                        msg += ' (Coordinates banner included; zoom in if map tiles were still loading.)';
                    }
                    showGpsToast(msg, 'success');
                    done();
                }

                try {
                    var tileCapture = captureWithLeafletTiles(map, mapWrap, coords);
                    if (tileCapture.tilesDrawn > 0) {
                        onSuccess(tileCapture.canvas, true);
                        return;
                    }
                } catch (e) { /* try html2canvas */ }

                var h2c = getHtml2CanvasLib();
                if (h2c) {
                    captureWithHtml2Canvas(mapWrap, captureLabel, coords, map)
                        .then(function (canvas) { onSuccess(canvas, true); })
                        .catch(function () {
                            try {
                                var fallback = captureWithLeafletTiles(map, mapWrap, coords);
                                onSuccess(fallback.canvas, fallback.tilesDrawn > 0);
                            } catch (e2) {
                                showGpsToast('Could not capture the map. Wait for tiles to load, then try again.', 'warning');
                                done();
                            }
                        });
                    return;
                }

                try {
                    var lastTry = captureWithLeafletTiles(map, mapWrap, coords);
                    onSuccess(lastTry.canvas, lastTry.tilesDrawn > 0);
                } catch (e3) {
                    showGpsToast('Capture is not available. Refresh the page and try again.', 'danger');
                    done();
                }
            }, 600);
        });
    }

    function resizeMap(map, center, zoom) {
        if (!map) return;
        map.invalidateSize();
        if (center) {
            map.setView(center, zoom !== undefined ? zoom : map.getZoom());
        }
    }

    function activateGpsTab() {
        var tabBtn = document.getElementById('quotation-gps-tab');
        if (!tabBtn || !global.bootstrap || !bootstrap.Tab) return false;
        bootstrap.Tab.getOrCreateInstance(tabBtn).show();
        return true;
    }

    function scrollToMap() {
        var wrap = document.getElementById('quotation-gps-map-wrap') || document.getElementById('quotation-gps-map-view-wrap');
        var mapEl = document.getElementById('quotation-gps-map') || document.getElementById('quotation-gps-map-view');
        (wrap || mapEl) && (wrap || mapEl).scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function whenMapVisible(mapEl, initFn) {
        if (!mapEl) return;

        function runInit() {
            requestAnimationFrame(function () {
                requestAnimationFrame(initFn);
            });
        }

        if (isVisible(mapEl)) {
            runInit();
            return;
        }

        var tabPane = mapEl.closest('.tab-pane');
        if (tabPane && tabPane.id) {
            var tabTrigger = document.querySelector('[data-bs-target="#' + tabPane.id + '"]');
            if (tabTrigger) {
                tabTrigger.addEventListener('shown.bs.tab', function () {
                    runInit();
                }, { once: true });
                return;
            }
        }

        var modal = mapEl.closest('.modal');
        if (modal) {
            modal.addEventListener('shown.bs.modal', function () {
                runInit();
            }, { once: true });
            return;
        }

        runInit();
    }

    function bindTabResize(mapEl, map, getCenter) {
        var tabPane = mapEl.closest('.tab-pane');
        if (!tabPane || !tabPane.id) return;
        var tabTrigger = document.querySelector('[data-bs-target="#' + tabPane.id + '"]');
        if (!tabTrigger) return;
        tabTrigger.addEventListener('shown.bs.tab', function () {
            resizeMap(map, getCenter ? getCenter() : null);
        });
    }

    function bindModalResize(mapEl, map, getCenter) {
        var modal = mapEl.closest('.modal');
        if (!modal) return;
        modal.addEventListener('shown.bs.modal', function () {
            resizeMap(map, getCenter ? getCenter() : null);
        });
    }

    function consumePendingFly(handler) {
        if (!pendingFly) return;
        var target = pendingFly;
        pendingFly = null;
        handler(target.lat, target.lng);
    }

    function initPicker(opts) {
        var mapEl = document.getElementById(opts.mapId);
        if (!mapEl) return;

        var mapWrap = opts.mapWrapId ? document.getElementById(opts.mapWrapId) : mapEl.parentElement;

        whenMapVisible(mapEl, function () {
            if (mapEl.dataset.gpsMapReady === '1') {
                if (global.__quotationGpsPicker) {
                    consumePendingFly(global.__quotationGpsPicker.setMarkerAt);
                }
                if (global.__quotationGpsMap) resizeMap(global.__quotationGpsMap);
                return;
            }

            var latIn = document.getElementById(opts.latInputId);
            var lngIn = document.getElementById(opts.lngInputId);
            var readout = document.getElementById(opts.readoutId);
            var initialLat = parseCoord(opts.initialLat);
            var initialLng = parseCoord(opts.initialLng);

            var center = DEFAULT_CENTER.slice();
            var zoom = DEFAULT_ZOOM;
            if (initialLat !== null && initialLng !== null) {
                center = [initialLat, initialLng];
                zoom = DETAIL_ZOOM;
            }

            var mapBundle = createMap(mapEl, center, zoom);
            var map = mapBundle.map;
            global.__quotationGpsMap = map;
            mapEl.dataset.gpsMapReady = '1';

            var marker = null;

            function updateInputs(lat, lng) {
                if (latIn) latIn.value = lat.toFixed(7);
                if (lngIn) lngIn.value = lng.toFixed(7);
                if (readout) readout.textContent = lat.toFixed(6) + ', ' + lng.toFixed(6);
            }

            function clearPin() {
                if (marker) {
                    map.removeLayer(marker);
                    marker = null;
                }
                if (latIn) latIn.value = '';
                if (lngIn) lngIn.value = '';
                if (readout) readout.textContent = '—';
                renderQuotationCoordsHint(null, null, false);
            }

            function setMarker(latLng, skipInputUpdate) {
                if (!marker) {
                    marker = L.marker(latLng, { draggable: true }).addTo(map);
                    marker.on('dragend', function () {
                        var p = marker.getLatLng();
                        updateInputs(p.lat, p.lng);
                    });
                } else {
                    marker.setLatLng(latLng);
                }
                if (!skipInputUpdate) {
                    updateInputs(latLng.lat, latLng.lng);
                }
            }

            function setMarkerAt(lat, lng) {
                lat = parseCoord(lat);
                lng = parseCoord(lng);
                if (lat === null || lng === null) return;
                var latLng = L.latLng(lat, lng);
                setMarker(latLng, true);
                updateInputs(lat, lng);
                map.setView(latLng, Math.min(DETAIL_ZOOM, map.getMaxZoom()));
                resizeMap(map, latLng, Math.min(DETAIL_ZOOM, map.getMaxZoom()));
            }

            function getCurrentCoords() {
                if (marker) {
                    var p = marker.getLatLng();
                    return { lat: p.lat, lng: p.lng };
                }
                var lat = parseCoord(latIn && latIn.value);
                var lng = parseCoord(lngIn && lngIn.value);
                if (lat !== null && lng !== null) return { lat: lat, lng: lng };
                return null;
            }

            function applyToQuotation() {
                var coords = getCurrentCoords();
                if (!coords) {
                    showGpsToast('Place a pin on the map first, then load coordinates on the quotation.', 'warning');
                    if (readout) {
                        readout.classList.add('text-danger');
                        setTimeout(function () { readout.classList.remove('text-danger'); }, 1500);
                    }
                    return false;
                }
                renderQuotationCoordsHint(coords.lat, coords.lng, true);
                showGpsToast(
                    '<strong>Coordinates loaded on quotation</strong><br>'
                    + formatCoords(coords.lat, coords.lng)
                    + '<br><span class="small">Shown under Project Location on the Details tab.</span>',
                    'success'
                );
                var tabBtn = document.getElementById('quotation-details-tab');
                if (tabBtn && global.bootstrap && bootstrap.Tab) {
                    bootstrap.Tab.getOrCreateInstance(tabBtn).show();
                }
                var locField = document.getElementById('project_location')
                    || document.querySelector('[name="project_location"]')
                    || document.querySelector('[name="location"]');
                if (locField) {
                    setTimeout(function () {
                        locField.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }, 300);
                }
                return true;
            }

            map.on('click', function (e) {
                setMarker(e.latlng);
            });

            var clr = document.getElementById(opts.clearButtonId);
            if (clr) clr.addEventListener('click', clearPin);

            var applyBtn = document.getElementById(opts.applyButtonId);
            if (applyBtn) applyBtn.addEventListener('click', applyToQuotation);

            if (initialLat !== null && initialLng !== null) {
                setMarker(L.latLng(initialLat, initialLng));
            }

            var uiCtx = {
                map: map,
                mapWrap: mapWrap,
                hdButtonId: opts.hdButtonId,
                captureButtonId: opts.captureButtonId,
                captureLabelId: opts.captureLabelId,
                getCoords: getCurrentCoords
            };
            bindMapUi(uiCtx);

            global.__quotationGpsPicker = {
                map: map,
                setMarkerAt: setMarkerAt,
                getCurrentCoords: getCurrentCoords,
                applyToQuotation: applyToQuotation
            };

            consumePendingFly(setMarkerAt);

            function getCenter() {
                if (marker) return marker.getLatLng();
                return L.latLng(center[0], center[1]);
            }

            bindTabResize(mapEl, map, getCenter);
            bindModalResize(mapEl, map, getCenter);
            resizeMap(map, L.latLng(center[0], center[1]));
        });
    }

    function initView(opts) {
        var mapEl = document.getElementById(opts.mapId);
        if (!mapEl) return;

        var mapWrap = opts.mapWrapId ? document.getElementById(opts.mapWrapId) : mapEl.parentElement;

        var lat = parseCoord(opts.lat);
        var lng = parseCoord(opts.lng);
        var hasPin = lat !== null && lng !== null;
        if (!hasPin) {
            lat = DEFAULT_CENTER[0];
            lng = DEFAULT_CENTER[1];
        }

        whenMapVisible(mapEl, function () {
            if (mapEl.dataset.gpsMapReady === '1') {
                if (global.__quotationGpsView) {
                    consumePendingFly(global.__quotationGpsView.showAt);
                }
                if (mapEl._gpsViewMap) resizeMap(mapEl._gpsViewMap, L.latLng(lat, lng));
                return;
            }

            var center = [lat, lng];
            var mapBundle = createMap(mapEl, center, hasPin ? DETAIL_ZOOM : DEFAULT_ZOOM);
            var map = mapBundle.map;
            var marker = null;
            if (hasPin) {
                marker = L.marker(center, { draggable: false }).addTo(map);
            }
            mapEl.dataset.gpsMapReady = '1';
            mapEl._gpsViewMap = map;

            function showAt(targetLat, targetLng) {
                targetLat = parseCoord(targetLat);
                targetLng = parseCoord(targetLng);
                if (targetLat === null || targetLng === null) return;
                var latLng = L.latLng(targetLat, targetLng);
                if (!marker) {
                    marker = L.marker(latLng, { draggable: false }).addTo(map);
                } else {
                    marker.setLatLng(latLng);
                }
                map.setView(latLng, Math.min(DETAIL_ZOOM, map.getMaxZoom()));
                resizeMap(map, latLng, Math.min(DETAIL_ZOOM, map.getMaxZoom()));
            }

            bindMapUi({
                map: map,
                mapWrap: mapWrap,
                hdButtonId: opts.hdButtonId,
                captureButtonId: opts.captureButtonId,
                captureLabelId: opts.captureLabelId,
                getCoords: function () {
                    if (marker) {
                        var p = marker.getLatLng();
                        return { lat: p.lat, lng: p.lng };
                    }
                    return hasPin ? { lat: lat, lng: lng } : null;
                }
            });

            global.__quotationGpsView = { map: map, showAt: showAt };
            consumePendingFly(showAt);

            var centerLatLng = L.latLng(lat, lng);
            bindTabResize(mapEl, map, function () { return centerLatLng; });
            bindModalResize(mapEl, map, function () { return centerLatLng; });
            resizeMap(map, centerLatLng);
        });
    }

    function showOnMap(lat, lng) {
        lat = parseCoord(lat);
        lng = parseCoord(lng);
        if (lat === null || lng === null) return;

        pendingFly = { lat: lat, lng: lng };
        var usedTab = activateGpsTab();

        function tryShow() {
            if (global.__quotationGpsPicker) {
                global.__quotationGpsPicker.setMarkerAt(lat, lng);
                pendingFly = null;
                scrollToMap();
                return;
            }
            if (global.__quotationGpsView) {
                global.__quotationGpsView.showAt(lat, lng);
                pendingFly = null;
                scrollToMap();
                return;
            }

            var mapEl = document.getElementById('quotation-gps-map') || document.getElementById('quotation-gps-map-view');
            if (mapEl) {
                whenMapVisible(mapEl, function () {
                    if (global.__quotationGpsPicker) {
                        global.__quotationGpsPicker.setMarkerAt(lat, lng);
                        pendingFly = null;
                    } else if (global.__quotationGpsView) {
                        global.__quotationGpsView.showAt(lat, lng);
                        pendingFly = null;
                    }
                    scrollToMap();
                });
            } else if (!usedTab) {
                pendingFly = null;
            }
        }

        if (usedTab) {
            var tabBtn = document.getElementById('quotation-gps-tab');
            if (tabBtn) {
                tabBtn.addEventListener('shown.bs.tab', function () {
                    tryShow();
                }, { once: true });
            }
            setTimeout(tryShow, 350);
        } else {
            tryShow();
        }
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest('.quotation-gps-coords-link');
        if (!link) return;
        e.preventDefault();
        showOnMap(link.getAttribute('data-lat'), link.getAttribute('data-lng'));
    });

    global.QuotationGpsMap = {
        registerPicker: function (opts) {
            whenReady(function () { initPicker(opts); });
        },
        registerView: function (opts) {
            whenReady(function () { initView(opts); });
        },
        applyToQuotation: function () {
            if (global.__quotationGpsPicker) {
                return global.__quotationGpsPicker.applyToQuotation();
            }
            return false;
        },
        showOnMap: showOnMap,
        renderQuotationCoordsHint: renderQuotationCoordsHint,
        showToast: showGpsToast
    };
})(window);
