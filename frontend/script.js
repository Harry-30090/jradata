// ===== CONFIG =====
const BASE_URL = "../data"; // if frontend and data are at same level
// If you move data into frontend folder, set "./data"

// const DATE_LIST = ["2025-11-02"]; // for testing; add dates or generate dynamically

// ===== HELPERS =====

async function fetchJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

// ===== MASTER LOADING =====

async function loadMasterData() {
  try {
    const today = document.getElementById("dateSelect").value;
    const path = `${BASE_URL}/${today}/master.json`;
    const data = await fetchJson(path);
    console.log("✅ Loaded master.json:", data);
    populatePlaces(data.places);
    document.getElementById("status").textContent = `Loaded ${data.places.length} places for ${data.date}`;
  } catch (err) {
    console.error("❌ Failed to load master.json:", err);
    document.getElementById("status").textContent = `Failed to load master.json: ${err.message}`;
  }
}

// ===== UI: Dates =====

async function populateDates() {
  const select = document.getElementById("dateSelect");
  select.innerHTML = "";

  try {
    // Fetch directory listing from ../data/
    const res = await fetch("../data/");
    const html = await res.text();

    // Parse directory listing (works with python -m http.server or GitHub Pages)
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    // Extract folder names that look like dates
    const dateFolders = Array.from(doc.querySelectorAll("a"))
      .map(a => a.getAttribute("href"))
      .filter(href => href && /^\d{4}-\d{2}-\d{2}\/$/.test(href))
      .map(href => href.replace("/", ""))
      .sort()
      .reverse(); // newest first

    if (dateFolders.length === 0) {
      throw new Error("No data folders found.");
    }

    // Populate dropdown
    dateFolders.forEach(date => {
      const opt = document.createElement("option");
      opt.value = date;
      opt.textContent = date;
      select.appendChild(opt);
    });

    // Auto-select latest
    select.value = dateFolders[0];

    // Auto-load master.json for the latest date
    await loadMasterData();
  } catch (err) {
    console.error("❌ Failed to load date folders dynamically:", err);

    // fallback to a manual test list
    const fallback = ["2025-11-02"];
    fallback.forEach(date => {
      const opt = document.createElement("option");
      opt.value = date;
      opt.textContent = date;
      select.appendChild(opt);
    });
    select.value = fallback[0];
    await loadMasterData();
  }
}

// ===== UI: Places (buttons) & Races (buttons) =====

function populatePlaces(places) {
  const container = document.getElementById("placeButtons");
  container.innerHTML = "";

  places.forEach((p, idx) => {
    const btn = document.createElement("button");
    btn.textContent = p.jp_name;
    btn.className =
      "px-4 py-2 rounded font-semibold border border-gray-300 bg-gray-100 text-gray-700 hover:bg-blue-600 hover:text-white transition";

    btn.addEventListener("click", () => {
      // Remove active from all
      document.querySelectorAll("#placeButtons button").forEach(b => {
        b.classList.remove("bg-blue-600", "text-white", "border-blue-700");
        b.classList.add("bg-gray-100", "text-gray-700", "border-gray-300");
      });
      // Add active styles
      btn.classList.remove("bg-gray-100", "text-gray-700", "border-gray-300");
      btn.classList.add("bg-blue-600", "text-white", "border-blue-700");

      populateRaces(p.races, p.name);
    });

    container.appendChild(btn);

    // Auto-select first one
    if (idx === 0) btn.click();
  });
}


function populateRaces(races, placeName) {
  const raceContainer = document.getElementById("raceButtons");
  raceContainer.innerHTML = "";

  races.forEach((r, i) => {
    const btn = document.createElement("button");
    btn.textContent = r;
    btn.className =
      "px-3 py-1 rounded-md border border-gray-300 hover:bg-green-600 hover:text-white transition";

    btn.addEventListener("click", () => {
      document.querySelectorAll("#raceButtons button").forEach((b) =>
        b.classList.remove("bg-green-600", "text-white")
      );
      btn.classList.add("bg-green-600", "text-white");
      loadRaceData(placeName, r);
    });

    raceContainer.appendChild(btn);

    // auto-select first
    if (i === 0) {
      btn.classList.add("bg-green-600", "text-white");
      loadRaceData(placeName, r);
    }
  });
}

// ===== RACE LOADING & RENDER =====

async function loadRaceData(place, race) {
  const today = document.getElementById("dateSelect").value;
  const tableBody = document.getElementById("oddsTableBody");
  const tableContainer = document.getElementById("tableContainer");

  // loading state
  tableBody.innerHTML = `<tr><td colspan="6" class="py-4 text-gray-500">Loading...</td></tr>`;
  tableContainer.classList.remove("hidden");
  document.getElementById("status").textContent = `Loading ${place} ${race}...`;

  try {
    const path = `${BASE_URL}/${today}/${place}_${race}.json`;
    const data = await fetchJson(path);

    renderTable(data);
    document.getElementById("status").textContent = `Showing ${place} ${race}`;
  } catch (err) {
    console.error("❌ Failed to load race JSON:", err);
    tableBody.innerHTML = `<tr><td colspan="6" class="py-4 text-red-500">Error loading race data</td></tr>`;
    document.getElementById("status").textContent = `Error loading ${place} ${race}`;
  }
}

function renderTable(data) {
  const tableBody = document.getElementById("oddsTableBody");
  tableBody.innerHTML = "";

  const numColors = {
    1:  "rgb(220, 20, 60)",
    2:  "rgb(0, 100, 200)",
    3:  "rgb(0, 150, 70)",
    4:  "rgb(255, 140, 0)",
    5:  "rgb(128, 0, 128)",
    6:  "rgb(0, 180, 180)",
    7:  "rgb(255, 60, 130)",
    8:  "rgb(75, 0, 130)",
    9:  "rgb(139, 69, 19)",
    10: "rgb(50, 50, 50)",
    11: "rgb(0, 90, 100)",
    12: "rgb(34, 139, 34)",
    13: "rgb(180, 20, 120)",
    14: "rgb(0, 90, 160)",
    15: "rgb(200, 60, 0)",
    16: "rgb(90, 0, 0)",
    17: "rgb(0, 80, 80)",
    18: "rgb(100, 100, 0)",
  };

  data.forEach((row) => {
    const tr = document.createElement("tr");
    const cells = [
      row[0] ?? "N/A",
      row[1] ?? "N/A",
      row[2] ?? "N/A",
      row[3] ?? "N/A",
      row[4] ?? "N/A",
      row[5] ?? "N/A",
    ];

    cells.forEach((cell, idx) => {
      const td = document.createElement("td");
      td.textContent = cell;
      td.className = "border px-2 py-1";

      // "#" columns — make small squares with background color
      if (idx % 2 === 0) {
        const num = parseInt(cell);
        td.classList.add("font-semibold", "text-white");
        td.style.width = "2rem";
        td.style.height = "2rem";
        td.style.textAlign = "center";
        td.style.verticalAlign = "middle";
        td.style.backgroundColor = numColors[num] || "#ccc";
      } else {
        td.classList.add("px-3", "text-gray-800", "font-medium");
        td.style.width = "4rem";
      }

      tr.appendChild(td);
    });

    tableBody.appendChild(tr);
  });

  document.getElementById("tableContainer").classList.remove("hidden");
}



// ===== INIT =====

document.addEventListener("DOMContentLoaded", () => {
  // populate dates and load first master
  populateDates();
  loadMasterData();

  document.getElementById("dateSelect").addEventListener("change", loadMasterData);
});
