const state = {
    stream: null,
    imageBlob: null,
    captures: [],
};

const elements = {
    health: document.querySelector("#health-status"),
    captureState: document.querySelector("#capture-state"),
    camera: document.querySelector("#camera-stream"),
    image: document.querySelector("#captured-image"),
    empty: document.querySelector("#empty-preview"),
    startCamera: document.querySelector("#start-camera"),
    capturePhoto: document.querySelector("#capture-photo"),
    imageFile: document.querySelector("#image-file"),
    canvas: document.querySelector("#capture-canvas"),
    form: document.querySelector("#recognition-form"),
    runRecognition: document.querySelector("#run-recognition"),
    recognitionMessage: document.querySelector("#recognition-message"),
    deviceGrid: document.querySelector("#device-grid"),
    refreshDevices: document.querySelector("#refresh-devices"),
    captureGallery: document.querySelector("#capture-gallery"),
    captureCount: document.querySelector("#capture-count"),
};

function setMessage(message, isError = false) {
    elements.recognitionMessage.textContent = message;
    elements.recognitionMessage.style.color = isError ? "#f09a9c" : "#9aa9b8";
}

function setCapturePreview(src, blob) {
    state.imageBlob = blob;
    elements.image.src = src;
    elements.image.hidden = false;
    elements.empty.hidden = true;
    elements.camera.hidden = true;
    elements.runRecognition.disabled = false;
    elements.captureState.className = "status-dot ready";
    elements.captureState.setAttribute("aria-label", "Capture ready");
    console.info("Sentry Vision: image preview ready", { bytes: blob.size, type: blob.type });
}

async function checkHealth() {
    try {
        const response = await fetch("/api/v1/health/");
        if (!response.ok) throw new Error("API offline");
        elements.health.textContent = "API online";
        elements.health.className = "health-pill ok";
    } catch (error) {
        elements.health.textContent = "API offline";
        elements.health.className = "health-pill error";
    }
}

async function startCamera() {
    try {
        if (state.stream) {
            state.stream.getTracks().forEach((track) => track.stop());
        }
        state.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        elements.camera.srcObject = state.stream;
        elements.camera.hidden = false;
        elements.image.hidden = true;
        elements.empty.hidden = true;
        elements.capturePhoto.disabled = false;
        elements.captureState.className = "status-dot busy";
        elements.captureState.setAttribute("aria-label", "Camera active");
        setMessage("Camera ready. Take a photo when the face is in frame.");
    } catch (error) {
        setMessage("Camera access failed. Upload an image instead.", true);
    }
}

function capturePhoto() {
    const video = elements.camera;
    const canvas = elements.canvas;
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(video, 0, 0, width, height);
    canvas.toBlob((blob) => {
        if (!blob) {
            setMessage("Could not capture the frame.", true);
            return;
        }
        setCapturePreview(URL.createObjectURL(blob), blob);
        setMessage("Frame captured and ready to analyze.");
    }, "image/jpeg", 0.9);
}

function uploadPreview(event) {
    const file = event.target.files[0];
    if (!file) return;
    setCapturePreview(URL.createObjectURL(file), file);
    setMessage("Image loaded and ready to analyze.");
}

function formatConfidence(value) {
    const confidence = Number(value);
    if (!Number.isFinite(confidence)) return "Score —";
    return `Score ${Math.max(0, Math.min(100, confidence)).toFixed(confidence % 1 ? 1 : 0)}%`;
}

function statusForCapture(payload) {
    if (!payload.recognized) return "Unknown";
    return payload.authorization_status === "Authorized" ? "Authorized" : "Unauthorized";
}

function renderCaptures() {
    elements.captureCount.textContent = `${state.captures.length} capture${state.captures.length === 1 ? "" : "s"}`;
    if (!state.captures.length) {
        elements.captureGallery.className = "capture-gallery empty-gallery";
        elements.captureGallery.innerHTML = `
            <div class="gallery-empty">
                <span class="gallery-empty-icon">◌</span>
                <p>No captures yet</p>
                <small>Analyzed images will appear here.</small>
            </div>`;
        return;
    }

    elements.captureGallery.className = "capture-gallery";
    elements.captureGallery.innerHTML = state.captures.map((capture) => `
        <article class="face-card">
            <a class="face-image-link" href="${escapeHtml(capture.imageUrl)}" target="_blank" rel="noopener noreferrer">
                <img class="face-image" src="${escapeHtml(capture.imageUrl)}" alt="Captured face for ${escapeHtml(capture.name)}">
            </a>
            <div class="face-details">
                <div class="face-meta">
                    <p class="face-name">${escapeHtml(capture.name)}</p>
                    <span class="confidence">${escapeHtml(formatConfidence(capture.confidence))}</span>
                </div>
                <span class="face-status ${capture.status.toLowerCase()}">${escapeHtml(capture.status)}</span>
                <p class="face-time">${escapeHtml(capture.time)}</p>
                <a class="gallery-link" href="${escapeHtml(capture.imageUrl)}" target="_blank" rel="noopener noreferrer">Open image</a>
            </div>
        </article>`).join("");
}

function addCapture(payload) {
    const imageUrl = payload.image_url || elements.image.src;
    state.captures.unshift({
        imageUrl,
        name: payload.recognized ? (payload.name || "Possible match") : "Unknown",
        confidence: payload.confidence,
        status: statusForCapture(payload),
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    });
    renderCaptures();
    console.info("Sentry Vision: capture added to gallery", payload);
}

function captureFromLog(log) {
    const recognized = Boolean(log.recognized);
    return {
        imageUrl: log.image_url,
        name: recognized ? (log.personnel?.name || "Possible match") : "Unknown",
        confidence: log.confidence,
        status: recognized
            ? (log.authorization_status === "Authorized" ? "Authorized" : "Unauthorized")
            : "Unknown",
        time: formatDate(log.created_at),
    };
}

async function loadCaptureHistory() {
    try {
        const response = await fetch("/api/v1/detection-logs/?limit=100");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Capture history failed");

        state.captures = payload.logs
            .filter((log) => log.image_url)
            .map(captureFromLog);
        renderCaptures();
        console.info("Sentry Vision: loaded capture history", { count: state.captures.length });
    } catch (error) {
        console.error("Sentry Vision: could not load capture history", error);
        setMessage("Could not load previous captures.", true);
    }
}

async function runRecognition(event) {
    event.preventDefault();
    if (!state.imageBlob) {
        setMessage("Capture or upload an image first.", true);
        return;
    }

    elements.runRecognition.disabled = true;
    elements.captureState.className = "status-dot busy";
    setMessage("Analyzing capture...");

    try {
        const formData = new FormData();
        formData.append("image", state.imageBlob, "capture.jpg");
        console.info("Sentry Vision: sending image to recognition backend", { bytes: state.imageBlob.size });
        const response = await fetch("/api/v1/facial-recognition/", {
            method: "POST",
            body: formData,
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Recognition failed");

        console.info("Sentry Vision: recognition backend response", payload);
        addCapture(payload);
        elements.captureState.className = "status-dot ready";
        setMessage(payload.alert || "Capture added to the gallery.");
    } catch (error) {
        elements.captureState.className = "status-dot ready";
        setMessage(error.message, true);
    } finally {
        elements.runRecognition.disabled = false;
    }
}

function formatMetric(metric) {
    if (!metric || metric.value === null || metric.value === undefined) {
        return { name: "metric", value: "-", unit: "" };
    }
    return {
        name: metric.name || "metric",
        value: Number.isInteger(metric.value) ? metric.value : Number(metric.value).toFixed(1),
        unit: metric.unit || "",
    };
}

function formatDate(dateString) {
    if (!dateString) return "-";
    const parsed = Date.parse(dateString);
    if (Number.isNaN(parsed)) return dateString;
    return new Date(parsed).toLocaleString();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderDevice(device) {
    const metric = formatMetric(device.metric);
    const metadata = device.metadata || {};
    const metaText = Object.entries(metadata).map(([key, value]) => `${key}: ${value}`).join(" | ");
    const stateClass = String(device.status || "").toLowerCase();
    return `
        <article class="device-card">
            <header>
                <h3 class="device-name">${escapeHtml(device.device_name)}</h3>
                <span class="device-state ${escapeHtml(stateClass)}">${escapeHtml(device.status)}</span>
            </header>
            <p class="metric">${escapeHtml(metric.value)} <span>${escapeHtml(metric.unit)}</span></p>
            <p class="device-meta"><strong>${escapeHtml(metric.name)}</strong> · Last seen ${escapeHtml(formatDate(device.last_ping))}</p>
            <p class="device-meta">${escapeHtml(metaText || "No additional telemetry")}</p>
        </article>`;
}

async function loadDevices() {
    elements.deviceGrid.innerHTML = '<article class="device-card"><p class="device-meta">Loading devices...</p></article>';
    try {
        const response = await fetch("/api/v1/device-status/");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Device status failed");
        elements.deviceGrid.innerHTML = payload.devices.map(renderDevice).join("");
    } catch (error) {
        elements.deviceGrid.innerHTML = `<article class="device-card"><p class="device-meta">${escapeHtml(error.message)}</p></article>`;
    }
}

elements.startCamera.addEventListener("click", startCamera);
elements.capturePhoto.addEventListener("click", capturePhoto);
elements.imageFile.addEventListener("change", uploadPreview);
elements.form.addEventListener("submit", runRecognition);
elements.refreshDevices.addEventListener("click", loadDevices);

renderCaptures();
checkHealth();
loadDevices();
loadCaptureHistory();
