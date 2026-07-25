const state = {
    stream: null,
    imageBlob: null,
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
    label: document.querySelector("#label-select"),
    runRecognition: document.querySelector("#run-recognition"),
    recognizedFace: document.querySelector("#recognized-face"),
    authorizationStatus: document.querySelector("#authorization-status"),
    personName: document.querySelector("#person-name"),
    personRole: document.querySelector("#person-role"),
    personStatus: document.querySelector("#person-status"),
    recognitionMessage: document.querySelector("#recognition-message"),
    deviceGrid: document.querySelector("#device-grid"),
    refreshDevices: document.querySelector("#refresh-devices"),
};

const faceImages = {
    Kessie: "/static/personnel/kessie.svg",
    Anold: "/static/personnel/anold.svg",
    Faith: "/static/personnel/faith.svg",
    Misha: "/static/personnel/misha.svg",
    Luutu: "/static/personnel/luutu.svg",
    Unknown: "/static/personnel/unknown.svg",
};

function setMessage(message, isError = false) {
    elements.recognitionMessage.textContent = message;
    elements.recognitionMessage.style.color = isError ? "#b42318" : "#657384";
}

function setCapturePreview(src, blob) {
    state.imageBlob = blob;
    elements.image.src = src;
    elements.image.hidden = false;
    elements.empty.hidden = true;
    elements.camera.hidden = true;
    elements.captureState.className = "status-dot ready";
}

async function checkHealth() {
    try {
        const response = await fetch("/api/v1/health/");
        if (!response.ok) throw new Error("API offline");
        elements.health.textContent = "API Online";
        elements.health.className = "health-pill ok";
    } catch (error) {
        elements.health.textContent = "API Offline";
        elements.health.className = "health-pill error";
    }
}

async function startCamera() {
    try {
        state.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        elements.camera.srcObject = state.stream;
        elements.camera.hidden = false;
        elements.image.hidden = true;
        elements.empty.hidden = true;
        elements.capturePhoto.disabled = false;
        elements.captureState.className = "status-dot busy";
        setMessage("Camera ready.");
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
        setMessage("Frame captured.");
    }, "image/jpeg", 0.9);
}

function uploadPreview(event) {
    const file = event.target.files[0];
    if (!file) return;
    setCapturePreview(URL.createObjectURL(file), file);
    setMessage("Image loaded.");
}

function updateIdentity(payload) {
    const name = payload.name || "Unknown";
    const role = payload.role || "-";
    const status = payload.authorization_status || "Unauthorized";
    const recognized = Boolean(payload.recognized);

    elements.personName.textContent = recognized ? name : "Unknown";
    elements.personRole.textContent = recognized ? role : "-";
    elements.personStatus.textContent = status;
    elements.recognizedFace.src = faceImages[recognized ? name : "Unknown"] || faceImages.Unknown;

    elements.authorizationStatus.textContent = status;
    elements.authorizationStatus.className = "authorization-badge";
    if (status === "Authorized") {
        elements.authorizationStatus.classList.add("authorized");
    } else if (status === "Unauthorized") {
        elements.authorizationStatus.classList.add("unauthorized");
    } else {
        elements.authorizationStatus.classList.add("neutral");
    }
}

async function runRecognition(event) {
    event.preventDefault();
    elements.runRecognition.disabled = true;
    setMessage("Checking face...");

    try {
        let response;
        if (state.imageBlob) {
            const formData = new FormData();
            formData.append("label", elements.label.value);
            formData.append("image", state.imageBlob, "capture.jpg");
            response = await fetch("/api/v1/facial-recognition/", {
                method: "POST",
                body: formData,
            });
        } else {
            response = await fetch("/api/v1/facial-recognition/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ label: elements.label.value }),
            });
        }

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "Recognition failed");
        }

        updateIdentity(payload);
        setMessage(payload.alert || "Recognition complete.");
    } catch (error) {
        setMessage(error.message, true);
    } finally {
        elements.runRecognition.disabled = false;
    }
}

function formatMetric(metric) {
    if (!metric || metric.value === null || metric.value === undefined) {
        return { value: "-", unit: "" };
    }
    return {
        value: Number.isInteger(metric.value) ? metric.value : Number(metric.value).toFixed(1),
        unit: metric.unit || "",
    };
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
    const metaText = Object.entries(metadata)
        .map(([key, value]) => `${key}: ${value}`)
        .join(" | ");
    const stateClass = String(device.status || "").toLowerCase();

    return `
        <article class="device-card">
            <header>
                <h3 class="device-name">${escapeHtml(device.device_name)}</h3>
                <span class="device-state ${escapeHtml(stateClass)}">${escapeHtml(device.status)}</span>
            </header>
            <p class="metric">${escapeHtml(metric.value)} <span>${escapeHtml(metric.unit)}</span></p>
            <p class="device-meta">${escapeHtml(device.metric?.name || "metric")} · ${escapeHtml(device.last_ping || "-")}</p>
            <p class="device-meta">${escapeHtml(metaText || "No metadata")}</p>
        </article>
    `;
}

async function loadDevices() {
    elements.deviceGrid.innerHTML = '<article class="device-card"><p class="device-meta">Loading devices...</p></article>';
    try {
        const response = await fetch("/api/v1/device-status/");
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "Device status failed");
        }
        elements.deviceGrid.innerHTML = payload.devices.map(renderDevice).join("");
    } catch (error) {
        elements.deviceGrid.innerHTML = `<article class="device-card"><p class="device-meta">${error.message}</p></article>`;
    }
}

elements.startCamera.addEventListener("click", startCamera);
elements.capturePhoto.addEventListener("click", capturePhoto);
elements.imageFile.addEventListener("change", uploadPreview);
elements.form.addEventListener("submit", runRecognition);
elements.refreshDevices.addEventListener("click", loadDevices);

checkHealth();
loadDevices();
