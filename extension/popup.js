const DEFAULT_THRESHOLD = 0.45;

const toggle = document.getElementById("toggle");
const threshold = document.getElementById("threshold");
const thresholdValue = document.getElementById("threshold-value");

function render(enabled) {
  toggle.textContent = enabled ? "Detection: ON" : "Detection: OFF";
  toggle.className = enabled ? "on" : "off";
}

function renderThreshold(value) {
  threshold.value = value;
  thresholdValue.textContent = Number(value).toFixed(2);
}

chrome.storage.local.get(
  { enabled: true, threshold: DEFAULT_THRESHOLD },
  (data) => {
    render(data.enabled);
    renderThreshold(data.threshold);
  }
);

toggle.addEventListener("click", () => {
  chrome.storage.local.get({ enabled: true }, (data) => {
    const enabled = !data.enabled;
    chrome.storage.local.set({ enabled });
    render(enabled);
  });
});

// Persist on every slider move; background.js reads it for each request, so the
// next capture picks up the new threshold automatically.
threshold.addEventListener("input", () => {
  const value = Number(threshold.value);
  thresholdValue.textContent = value.toFixed(2);
  chrome.storage.local.set({ threshold: value });
});
