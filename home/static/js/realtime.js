// ================================
// GLOBAL REALTIME DASHBOARD UPDATER (v2)
// ================================

// Fungsi utama untuk ambil dan update data dari server
async function updateRealtime() {
    try {
        const response = await fetch("/api/yolo-data/");
        if (!response.ok) throw new Error("HTTP " + response.status);

        const data = await response.json();

        // Debug (cek di console browser)
        console.log("✅ Realtime data:", data);

        // Update elemen angka di halaman (jika ada)
        updateText("motor-count", data.motor);
        updateText("mobil-count", data.mobil);
        updateText("pelanggar-count", data.pelanggar);
        updateText("total-count", data.total);
        updateText("last-update", data.last_update || "Belum ada update");

        // Jika ada chart handler (Chart.js)
        if (typeof updateCharts === "function") {
            updateCharts(data);
        }

    } catch (error) {
        console.warn("⚠️ Realtime fetch error:", error.message);
    }
}

// Fungsi helper update teks angka
function updateText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;

    // Animasi perubahan angka (lebih smooth)
    const oldValue = parseInt(el.innerText || "0", 10);
    if (oldValue !== value) {
        el.innerText = value;
        el.style.transition = "color 0.3s ease";
        el.style.color = "#2563eb";
        setTimeout(() => (el.style.color = ""), 600);
    }
}

// Jalankan setiap 1 detik (auto refresh realtime)
setInterval(updateRealtime, 1000);

// Jalankan segera ketika halaman pertama kali dibuka
document.addEventListener("DOMContentLoaded", updateRealtime);
