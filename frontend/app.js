/**
 * Sewa Setu ID Card Verification — Frontend Controller
 * Clear, simple, and friendly English for citizens and reviewers.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs & Views
  const navLiveTab = document.getElementById("navLiveTab");
  const navRecordsTab = document.getElementById("navRecordsTab");
  const liveVerifyView = document.getElementById("liveVerifyView");
  const recordsView = document.getElementById("recordsView");
  const recordCountBadge = document.getElementById("recordCountBadge");

  // Ingestion Dropzones
  const frontDropzone = document.getElementById("frontDropzone");
  const frontFileInput = document.getElementById("frontFileInput");
  const frontDropContent = document.getElementById("frontDropContent");
  const frontPreview = document.getElementById("frontPreview");
  const frontThumb = document.getElementById("frontThumb");
  const frontFileName = document.getElementById("frontFileName");
  const removeFrontBtn = document.getElementById("removeFrontBtn");

  const backDropzone = document.getElementById("backDropzone");
  const backFileInput = document.getElementById("backFileInput");
  const backDropContent = document.getElementById("backDropContent");
  const backPreview = document.getElementById("backPreview");
  const backThumb = document.getElementById("backThumb");
  const backFileName = document.getElementById("backFileName");
  const removeBackBtn = document.getElementById("removeBackBtn");

  // Form Fields
  const verifyForm = document.getElementById("verifyForm");
  const inputName = document.getElementById("inputName");
  const inputDob = document.getElementById("inputDob");
  const inputGender = document.getElementById("inputGender");
  const inputId = document.getElementById("inputId");
  const inputAddress = document.getElementById("inputAddress");
  const checkDeskew = document.getElementById("checkDeskew");
  const submitBtn = document.getElementById("submitBtn");

  // Sample Buttons
  const presetLeelaBtn = document.getElementById("presetLeelaBtn");
  const presetMockBtn = document.getElementById("presetMockBtn");
  const presetClearBtn = document.getElementById("presetClearBtn");

  // Results Elements
  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const loadingText = document.getElementById("loadingText");
  const resultsContent = document.getElementById("resultsContent");
  const storageRecordPill = document.getElementById("storageRecordPill");
  const savedRecordId = document.getElementById("savedRecordId");
  const btnCopyRecordId = document.getElementById("btnCopyRecordId");

  const tierCard = document.getElementById("tierCard");
  const tierBadge = document.getElementById("tierBadge");
  const reviewPriorityPill = document.getElementById("reviewPriorityPill");
  const tierTitle = document.getElementById("tierTitle");
  const tierDesc = document.getElementById("tierDesc");
  const scoreVal = document.getElementById("scoreVal");
  const scoreCircleProgress = document.getElementById("scoreCircleProgress");
  const policyNoticeText = document.getElementById("policyNoticeText");

  // Document Viewer Elements
  const docTabs = document.getElementById("docTabs");
  const tabFrontBtn = document.getElementById("tabFrontBtn");
  const tabBackBtn = document.getElementById("tabBackBtn");
  const docAnnotatedFront = document.getElementById("docAnnotatedFront");
  const docAnnotatedBack = document.getElementById("docAnnotatedBack");

  // Crop Grid & JSON Elements
  const cropGrid = document.getElementById("cropGrid");
  const fieldCountBadge = document.getElementById("fieldCountBadge");
  const jsonOutput = document.getElementById("jsonOutput");
  const copyJsonBtn = document.getElementById("copyJsonBtn");

  // Past Records Elements
  const statTotalRecs = document.getElementById("statTotalRecs");
  const statHighRecs = document.getElementById("statHighRecs");
  const statMedRecs = document.getElementById("statMedRecs");
  const statCritRecs = document.getElementById("statCritRecs");
  const recordsSearchInput = document.getElementById("recordsSearchInput");
  const btnSearchClear = document.getElementById("btnSearchClear");
  const recordsTierFilter = document.getElementById("recordsTierFilter");
  const refreshRecordsBtn = document.getElementById("refreshRecordsBtn");
  const recordsTableBody = document.getElementById("recordsTableBody");
  const noRecordsMsg = document.getElementById("noRecordsMsg");

  // Modal Elements
  const auditModal = document.getElementById("auditModal");
  const btnModalClose = document.getElementById("btnModalClose");
  const modalRecordTitle = document.getElementById("modalRecordTitle");
  const modalRecordSub = document.getElementById("modalRecordSub");
  const modalBody = document.getElementById("modalBody");

  // Toast Container
  const toastHub = document.getElementById("toastHub");

  let currentVerification = null;

  // ---------------------------------------------------------------------------
  // Color Themes (Dark, Light, Sapphire)
  // ---------------------------------------------------------------------------
  const themeButtons = document.querySelectorAll(".btn-theme-opt");
  const savedTheme = localStorage.getItem("sewa_setu_theme") || "dark";
  setTheme(savedTheme);

  themeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTheme = btn.getAttribute("data-set-theme");
      setTheme(targetTheme);
      showToast(`Switched to ${targetTheme.toUpperCase()} color view`, "info");
    });
  });

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sewa_setu_theme", theme);
    themeButtons.forEach((b) => {
      if (b.getAttribute("data-set-theme") === theme) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }

  // ---------------------------------------------------------------------------
  // View Switcher (Check ID vs Past Records)
  // ---------------------------------------------------------------------------

  navLiveTab.addEventListener("click", () => {
    navLiveTab.classList.add("active");
    navRecordsTab.classList.remove("active");
    liveVerifyView.style.display = "block";
    recordsView.style.display = "none";
  });

  navRecordsTab.addEventListener("click", () => {
    navRecordsTab.classList.add("active");
    navLiveTab.classList.remove("active");
    liveVerifyView.style.display = "none";
    recordsView.style.display = "block";
    loadRecords();
    loadStorageStats();
  });

  // ---------------------------------------------------------------------------
  // Document Viewer Color Background & Zoom
  // ---------------------------------------------------------------------------
  const viewerViewport = document.getElementById("viewerViewport");
  const btnBgDark = document.getElementById("btnBgDark");
  const btnBgLight = document.getElementById("btnBgLight");
  const btnZoomIn = document.getElementById("btnZoomIn");
  const btnZoomOut = document.getElementById("btnZoomOut");
  const btnZoomReset = document.getElementById("btnZoomReset");

  let currentZoom = 1.0;

  if (btnBgDark && btnBgLight && viewerViewport) {
    btnBgDark.addEventListener("click", () => {
      viewerViewport.classList.remove("bg-viewport-light");
      viewerViewport.classList.add("bg-viewport-dark");
      btnBgDark.classList.add("active");
      btnBgLight.classList.remove("active");
    });

    btnBgLight.addEventListener("click", () => {
      viewerViewport.classList.remove("bg-viewport-dark");
      viewerViewport.classList.add("bg-viewport-light");
      btnBgLight.classList.add("active");
      btnBgDark.classList.remove("active");
    });
  }

  function applyZoom() {
    [docAnnotatedFront, docAnnotatedBack].forEach((img) => {
      if (img) img.style.transform = `scale(${currentZoom})`;
    });
  }

  if (btnZoomIn) {
    btnZoomIn.addEventListener("click", () => {
      if (currentZoom < 2.5) {
        currentZoom = +(currentZoom + 0.25).toFixed(2);
        applyZoom();
      }
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener("click", () => {
      if (currentZoom > 0.6) {
        currentZoom = +(currentZoom - 0.25).toFixed(2);
        applyZoom();
      }
    });
  }

  if (btnZoomReset) {
    btnZoomReset.addEventListener("click", () => {
      currentZoom = 1.0;
      applyZoom();
    });
  }

  // Interactive Legend Click -> Scrolls & Pulses matching crop card
  document.querySelectorAll(".legend-tag").forEach((tag) => {
    tag.addEventListener("click", () => {
      const field = tag.getAttribute("data-field");
      if (!field) return;
      const targetCard = document.querySelector(`.crop-card[data-card-field="${field}"]`);
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
        targetCard.style.outline = "2px solid var(--color-primary)";
        targetCard.style.boxShadow = "0 0 20px var(--color-primary-glow)";
        setTimeout(() => {
          targetCard.style.outline = "";
          targetCard.style.boxShadow = "";
        }, 1800);
      }
    });
  });

  // ---------------------------------------------------------------------------
  // Dropzone Helpers & Handlers
  // ---------------------------------------------------------------------------

  function setupDropzone(dropzone, input, content, preview, thumb, nameLabel) {
    dropzone.addEventListener("click", (e) => {
      if (!e.target.closest(".btn-icon-remove")) {
        input.click();
      }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        input.files = e.dataTransfer.files;
        handleFileSelect(input.files[0], content, preview, thumb, nameLabel);
      }
    });

    input.addEventListener("change", () => {
      if (input.files && input.files.length > 0) {
        handleFileSelect(input.files[0], content, preview, thumb, nameLabel);
      }
    });
  }

  function handleFileSelect(file, content, preview, thumb, nameLabel) {
    if (!file) return;
    nameLabel.textContent = file.name;
    content.style.display = "none";
    preview.style.display = "flex";

    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => {
        thumb.src = e.target.result;
        thumb.style.display = "block";
      };
      reader.readAsDataURL(file);
    } else {
      // PDF document icon thumbnail
      thumb.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 24 24' fill='%23ef4444'><path d='M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9.5 8.5h-2v1h2c.28 0 .5-.22.5-.5s-.22-.5-.5-.5zm5 0h-2v2h2c.28 0 .5-.22.5-.5v-1c0-.28-.22-.5-.5-.5zM19 19H5V5h14v14z'/></svg>";
      thumb.style.display = "block";
    }
  }

  setupDropzone(frontDropzone, frontFileInput, frontDropContent, frontPreview, frontThumb, frontFileName);
  setupDropzone(backDropzone, backFileInput, backDropContent, backPreview, backThumb, backFileName);

  removeFrontBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    frontFileInput.value = "";
    frontPreview.style.display = "none";
    frontDropContent.style.display = "flex";
  });

  removeBackBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    backFileInput.value = "";
    backPreview.style.display = "none";
    backDropContent.style.display = "flex";
  });

  // ---------------------------------------------------------------------------
  // 1-Click Sample Demos (Real Image Attachments + Form Data)
  // ---------------------------------------------------------------------------

  async function attachSampleFileToInput(input, url, filename, content, preview, thumb, nameLabel) {
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const file = new File([blob], filename, { type: blob.type || "image/png" });
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      handleFileSelect(file, content, preview, thumb, nameLabel);
    } catch (err) {
      console.warn("Could not load sample file:", err);
    }
  }

  presetLeelaBtn.addEventListener("click", async () => {
    inputName.value = "Bokam Leeladhar";
    inputDob.value = "2003";
    inputGender.value = "Male";
    inputId.value = "5513 1404 1007";
    inputAddress.value = "1-63/b, Gullepalli, Sabbavaram Mandalam, Gullipalle, Visakhapatnam, Andhra Pradesh - 531035";

    showToast("⚡ Loading sample Aadhaar photos...", "info");

    await attachSampleFileToInput(
      frontFileInput,
      "/static/samples/sample_aadhaar_front.png",
      "aadhaar_front.png",
      frontDropContent,
      frontPreview,
      frontThumb,
      frontFileName
    );

    await attachSampleFileToInput(
      backFileInput,
      "/static/samples/sample_aadhaar_back.png",
      "aadhaar_back.png",
      backDropContent,
      backPreview,
      backThumb,
      backFileName
    );

    showToast("✅ Sample Aadhaar loaded! Click 'Check Document & Save' to test.", "success");
  });

  presetMockBtn.addEventListener("click", async () => {
    inputName.value = "Jonathan Doe";
    inputDob.value = "15/05/1990";
    inputGender.value = "Male";
    inputId.value = "ABCDE1234F";
    inputAddress.value = "123 Main Road, Apt 4B, Metro City 110001";

    removeBackBtn.click();

    showToast("⚡ Loading sample ID card photo...", "info");

    await attachSampleFileToInput(
      frontFileInput,
      "/static/samples/sample_id_card.png",
      "citizen_id_front.png",
      frontDropContent,
      frontPreview,
      frontThumb,
      frontFileName
    );

    showToast("✅ Sample ID loaded! Click 'Check Document & Save' to test.", "success");
  });

  presetClearBtn.addEventListener("click", () => {
    inputName.value = "";
    inputDob.value = "";
    inputGender.value = "";
    inputId.value = "";
    inputAddress.value = "";
    removeFrontBtn.click();
    removeBackBtn.click();
    showToast("🧹 All fields and photos cleared.", "info");
  });

  // ---------------------------------------------------------------------------
  // Form Submission & Verification Call
  // ---------------------------------------------------------------------------

  verifyForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!frontFileInput.files || frontFileInput.files.length === 0) {
      showToast("⚠️ Front side photo is required. Please upload a photo.", "error");
      frontDropzone.classList.add("dragover");
      setTimeout(() => frontDropzone.classList.remove("dragover"), 1200);
      return;
    }

    const formData = new FormData();
    formData.append("front_file", frontFileInput.files[0]);

    if (backFileInput.files && backFileInput.files.length > 0) {
      formData.append("back_file", backFileInput.files[0]);
    }

    if (inputName.value.trim()) formData.append("name", inputName.value.trim());
    if (inputDob.value.trim()) formData.append("dob", inputDob.value.trim());
    if (inputGender.value.trim()) formData.append("gender", inputGender.value.trim());
    if (inputId.value.trim()) formData.append("document_id", inputId.value.trim());
    if (inputAddress.value.trim()) formData.append("address", inputAddress.value.trim());
    formData.append("deskew", checkDeskew.checked);

    // Switch UI to checking state
    emptyState.style.display = "none";
    resultsContent.style.display = "none";
    loadingState.style.display = "flex";
    submitBtn.disabled = true;

    // Friendly progress steps
    let stepCount = 1;
    const interval = setInterval(() => {
      stepCount++;
      if (stepCount === 2 && loadingText) {
        loadingText.textContent = "Reading text from photo...";
      } else if (stepCount === 3 && loadingText) {
        loadingText.textContent = "Checking match & saving record...";
      }
    }, 900);

    try {
      const response = await fetch("/api/verify", {
        method: "POST",
        body: formData,
      });

      clearInterval(interval);

      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson.detail || "Server error while checking document.");
      }

      const data = await response.json();
      currentVerification = data;
      renderResults(data);
      loadStorageStats();
      showToast(`🎉 Check finished! Saved as record ID ${data.record_id}`, "success");
    } catch (err) {
      clearInterval(interval);
      console.error(err);
      showToast(`❌ Could not check document: ${err.message}`, "error");
      loadingState.style.display = "none";
      emptyState.style.display = "flex";
    } finally {
      submitBtn.disabled = false;
      if (loadingText) loadingText.textContent = "Checking your document...";
    }
  });

  // ---------------------------------------------------------------------------
  // Render Results in Simple English
  // ---------------------------------------------------------------------------

  function renderResults(data) {
    loadingState.style.display = "none";
    resultsContent.style.display = "flex";

    const audit = data.audit || {};
    const tier = audit.tier || "UNKNOWN";
    const overallScore = audit.overall_score || 0;
    const fields = audit.fields || {};

    // Record ID banner
    if (data.record_id && savedRecordId) {
      savedRecordId.textContent = data.record_id;
    }

    // Copy Record ID handler
    if (btnCopyRecordId) {
      btnCopyRecordId.onclick = () => {
        navigator.clipboard.writeText(data.record_id).then(() => {
          showToast(`📋 Copied record ID ${data.record_id}!`, "success");
        });
      };
    }

    // 1. Friendly Verdict & Match Score
    tierCard.className = "verdict-card";

    let strokeColor = "#10b981";
    reviewPriorityPill.style.display = "none";

    if (tier === "HIGH") {
      tierCard.classList.add("tier-high");
      tierBadge.textContent = "HIGH MATCH";
      tierBadge.style.color = "#10b981";
      tierBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
      tierTitle.textContent = "All Details Match";
      tierDesc.textContent = "All details on your card match the entered information.";
      strokeColor = "#10b981";
    } else if (tier === "MEDIUM") {
      tierCard.classList.add("tier-medium");
      tierBadge.textContent = "MEDIUM MATCH";
      tierBadge.style.color = "#f59e0b";
      tierBadge.style.borderColor = "rgba(245, 158, 11, 0.4)";
      tierTitle.textContent = "Details Mostly Match";
      tierDesc.textContent = "Minor differences were found (like abbreviations or short forms). Saved and accepted.";
      strokeColor = "#f59e0b";
    } else if (tier === "CRITICAL_MISMATCH") {
      tierCard.classList.add("tier-critical");
      tierBadge.textContent = "DIFFERENCE FOUND";
      tierBadge.style.color = "#f43f5e";
      tierBadge.style.borderColor = "rgba(244, 63, 94, 0.4)";
      reviewPriorityPill.style.display = "inline-flex";
      reviewPriorityPill.textContent = "⚠️ Officer Check Needed";
      tierTitle.textContent = "ID Number or Birth Date Does Not Match";
      tierDesc.textContent = "The ID number or birth date on the card is different from the form. Sent for manual officer check.";
      strokeColor = "#f43f5e";
    } else {
      tierCard.classList.add("tier-low");
      tierBadge.textContent = "NEEDS OFFICER CHECK";
      tierBadge.style.color = "#06b6d4";
      tierBadge.style.borderColor = "rgba(6, 182, 212, 0.4)";
      reviewPriorityPill.style.display = "inline-flex";
      reviewPriorityPill.textContent = "🔍 Blurry Photo";
      tierTitle.textContent = "Photo Hard to Read";
      tierDesc.textContent = "The photo was blurry or dark. An officer will check it by hand. It is NOT rejected.";
      strokeColor = "#06b6d4";
    }

    // Animate Circular Score Meter
    const targetOffset = 314 * (1 - Math.max(0, Math.min(100, overallScore)) / 100);
    scoreCircleProgress.style.stroke = strokeColor;
    scoreCircleProgress.style.strokeDashoffset = targetOffset;
    animateScoreNumber(scoreVal, overallScore);

    if (audit.policy_notice) {
      policyNoticeText.textContent = audit.policy_notice;
    }

    // 2. Document Bounding Box Viewer
    if (data.images && data.images.front_annotated) {
      docAnnotatedFront.src = data.images.front_annotated;
      docAnnotatedFront.style.display = "block";
    }

    if (data.images && data.images.back_annotated && data.meta && data.meta.has_back_document) {
      docAnnotatedBack.src = data.images.back_annotated;
      docTabs.style.display = "flex";
      tabFrontBtn.classList.add("active");
      tabBackBtn.classList.remove("active");
      docAnnotatedFront.style.display = "block";
      docAnnotatedBack.style.display = "none";
    } else {
      docTabs.style.display = "none";
      docAnnotatedBack.style.display = "none";
    }

    // 3. Field Snippets Grid
    cropGrid.innerHTML = "";
    const fieldKeys = Object.keys(fields);
    fieldCountBadge.textContent = `${fieldKeys.length} Details Checked`;

    const fieldDisplayNames = {
      name: "FULL NAME",
      dob: "DATE / YEAR OF BIRTH",
      gender: "GENDER",
      document_id: "ID NUMBER",
      address: "ADDRESS",
    };

    fieldKeys.forEach((fname) => {
      const fdata = fields[fname];
      const cropSrc = data.crops ? data.crops[fname] : null;
      const score = fdata.score || 0;
      const docSide = fdata.doc_side || "front";
      const sideText = docSide === "front" ? "Front Photo" : "Back Photo";
      const displayName = fieldDisplayNames[fname] || fname.replace("_", " ").toUpperCase();

      let scoreClass = "crop-match-high";
      if (score < 50) scoreClass = "crop-match-low";
      else if (score < 95) scoreClass = "crop-match-med";

      const card = document.createElement("div");
      card.className = "crop-card";
      card.setAttribute("data-card-field", fname);

      card.innerHTML = `
        <div class="crop-card-header">
          <div class="crop-field-title">
            <span>📌 ${displayName}</span>
            <span class="preview-tag">(${sideText})</span>
          </div>
          <span class="crop-match-pill ${scoreClass}">
            ${score.toFixed(0)}% MATCH
          </span>
        </div>

        <div class="crop-image-box">
          ${
            cropSrc
              ? `<img src="${cropSrc}" alt="Snippet of ${displayName}" class="crop-snippet-img">`
              : `<span style="font-size: 0.72rem; color: #64748b;">Photo Snippet</span>`
          }
        </div>

        <div class="crop-compare-table">
          <div class="compare-row">
            <span class="compare-lbl">You Entered:</span>
            <span class="compare-val">${escapeHtml(fdata.submitted || "N/A")}</span>
          </div>
          <div class="compare-row">
            <span class="compare-lbl">Found on Card:</span>
            <span class="compare-val mono">${escapeHtml(fdata.ocr_text || "N/A")}</span>
          </div>
          ${
            fdata.diff
              ? `<div class="compare-diff-tag">ℹ️ Difference: ${escapeHtml(fdata.diff)}</div>`
              : ""
          }
          <div class="compare-row" style="font-size: 0.7rem; color: #64748b;">
            <span>Location on photo:</span>
            <span class="mono">[${fdata.bbox?.join(", ") || "0, 0, 0, 0"}]</span>
          </div>
        </div>
      `;

      cropGrid.appendChild(card);
    });

    // 4. JSON Payload
    jsonOutput.textContent = JSON.stringify(audit, null, 2);
  }

  // Smooth number ticker animation
  function animateScoreNumber(element, finalValue) {
    let current = 0;
    const duration = 800;
    const steps = 25;
    const increment = finalValue / steps;
    const intervalTime = duration / steps;

    const timer = setInterval(() => {
      current += increment;
      if (current >= finalValue) {
        element.textContent = `${finalValue.toFixed(0)}%`;
        clearInterval(timer);
      } else {
        element.textContent = `${current.toFixed(0)}%`;
      }
    }, intervalTime);
  }

  // ---------------------------------------------------------------------------
  // Tab Switcher for Front/Back Bounding Boxes
  // ---------------------------------------------------------------------------

  tabFrontBtn.addEventListener("click", () => {
    tabFrontBtn.classList.add("active");
    tabBackBtn.classList.remove("active");
    docAnnotatedFront.style.display = "block";
    docAnnotatedBack.style.display = "none";
  });

  tabBackBtn.addEventListener("click", () => {
    tabBackBtn.classList.add("active");
    tabFrontBtn.classList.remove("active");
    docAnnotatedFront.style.display = "none";
    docAnnotatedBack.style.display = "block";
  });

  // ---------------------------------------------------------------------------
  // Past Records History (Simple & Clear)
  // ---------------------------------------------------------------------------

  async function loadStorageStats() {
    try {
      const res = await fetch("/api/storage/stats");
      if (!res.ok) return;
      const data = await res.json();
      const stats = data.stats || {};
      const count = stats.total_records || 0;

      if (statTotalRecs) statTotalRecs.textContent = count;
      if (recordCountBadge) recordCountBadge.textContent = count;

      const tb = stats.tier_breakdown || {};
      if (statHighRecs) statHighRecs.textContent = tb.HIGH || 0;
      if (statMedRecs) statMedRecs.textContent = tb.MEDIUM || 0;
      if (statCritRecs) statCritRecs.textContent = (tb.CRITICAL_MISMATCH || 0) + (tb.LOW || 0);
    } catch (e) {
      console.warn("Could not load stats:", e);
    }
  }

  async function loadRecords() {
    const tier = recordsTierFilter.value;
    const search = recordsSearchInput.value.trim();

    let url = `/api/records?limit=100`;
    if (tier && tier !== "ALL") url += `&tier=${encodeURIComponent(tier)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("Could not load records");
      const data = await res.json();
      renderRecordsTable(data.records || []);
    } catch (err) {
      console.error(err);
      showToast(`Could not load records: ${err.message}`, "error");
    }
  }

  function renderRecordsTable(records) {
    recordsTableBody.innerHTML = "";
    if (records.length === 0) {
      noRecordsMsg.style.display = "flex";
      return;
    }
    noRecordsMsg.style.display = "none";

    records.forEach((rec) => {
      const tr = document.createElement("tr");
      const dateObj = new Date(rec.timestamp);
      const formattedDate = dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      const formattedTime = dateObj.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

      const name = rec.applicant_name || "Anonymous";
      const initials = name
        .split(" ")
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase() || "ID";

      let chipClass = "chip-high";
      let chipText = "High Match";
      if (rec.tier === "MEDIUM") {
        chipClass = "chip-medium";
        chipText = "Mostly Match";
      } else if (rec.tier === "LOW") {
        chipClass = "chip-low";
        chipText = "Needs Review";
      } else if (rec.tier === "CRITICAL_MISMATCH") {
        chipClass = "chip-critical";
        chipText = "Difference Found";
      }

      const score = rec.overall_score || 0;

      tr.innerHTML = `
        <td class="td-record-id">${rec.id}</td>
        <td class="td-timestamp">
          <div>${formattedDate}</div>
          <div style="color: var(--text-tertiary); font-size: 0.72rem;">${formattedTime}</div>
        </td>
        <td>
          <div class="td-applicant">
            <div class="applicant-avatar">${initials}</div>
            <span class="applicant-name-text">${escapeHtml(name)}</span>
          </div>
        </td>
        <td class="td-doc-id">${escapeHtml(rec.document_id || "N/A")}</td>
        <td>
          <span class="tier-chip ${chipClass}">
            <span>●</span> ${chipText}
          </span>
        </td>
        <td>
          <div class="td-score-cell">
            <div class="score-bar-bg">
              <div class="score-bar-fill" style="width: ${Math.min(100, Math.max(0, score))}%; background: ${
                score >= 95 ? "#10b981" : score >= 50 ? "#f59e0b" : "#f43f5e"
              };"></div>
            </div>
            <span class="score-text">${score.toFixed(1)}%</span>
          </div>
        </td>
        <td>
          <div class="td-actions">
            <button type="button" class="btn-table-action btn-table-view" data-id="${rec.id}">
              <span>👁️</span> Inspect
            </button>
            <button type="button" class="btn-table-action btn-table-delete" data-id="${rec.id}" title="Delete record">
              <span>🗑️</span>
            </button>
          </div>
        </td>
      `;

      // Event listener for Inspect
      tr.querySelector(".btn-table-view").addEventListener("click", () => {
        openAuditModal(rec);
      });

      // Event listener for Delete
      tr.querySelector(".btn-table-delete").addEventListener("click", async () => {
        if (confirm(`Delete record ${rec.id}? This will remove it from saved history.`)) {
          await deleteRecord(rec.id);
        }
      });

      recordsTableBody.appendChild(tr);
    });
  }

  async function deleteRecord(recordId) {
    try {
      const res = await fetch(`/api/records/${recordId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      showToast(`🗑️ Record ${recordId} removed from saved history.`, "info");
      loadRecords();
      loadStorageStats();
    } catch (e) {
      showToast(`Delete failed: ${e.message}`, "error");
    }
  }

  // Open Details Modal
  function openAuditModal(rec) {
    modalRecordTitle.textContent = `Record Details: ${rec.id}`;
    modalRecordSub.textContent = `Citizen: ${rec.applicant_name || "N/A"} | ID: ${rec.document_id || "N/A"}`;

    const audit = rec.audit_json || {};
    const fields = audit.fields || {};
    const fieldKeys = Object.keys(fields);

    const fieldDisplayNames = {
      name: "FULL NAME",
      dob: "DATE / YEAR OF BIRTH",
      gender: "GENDER",
      document_id: "ID NUMBER",
      address: "ADDRESS",
    };

    modalBody.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(11, 18, 33, 0.7); padding: 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass);">
        <div>
          <span class="tier-pill" style="margin-right: 0.5rem;">${rec.tier}</span>
          <strong>Match Score: ${rec.overall_score?.toFixed(1)}%</strong>
        </div>
        <button type="button" class="btn-mini-action" id="btnLoadToLive" style="padding: 0.4rem 0.8rem;">
          🚀 Open in Live View
        </button>
      </div>

      <div style="font-size: 0.88rem; font-weight: 700; margin-top: 0.5rem;">Details Checked (${fieldKeys.length} Fields):</div>
      <div class="crop-cards-grid" style="grid-template-columns: 1fr 1fr;">
        ${fieldKeys
          .map((fname) => {
            const f = fields[fname];
            const displayName = fieldDisplayNames[fname] || fname.replace("_", " ").toUpperCase();
            return `
              <div class="crop-card">
                <div class="crop-card-header">
                  <strong>${displayName}</strong>
                  <span class="crop-match-pill ${f.score >= 95 ? "crop-match-high" : f.score >= 50 ? "crop-match-med" : "crop-match-low"}">
                    ${f.score?.toFixed(0) || 0}%
                  </span>
                </div>
                <div class="crop-compare-table">
                  <div class="compare-row">
                    <span class="compare-lbl">You Entered:</span>
                    <span class="compare-val">${escapeHtml(f.submitted || "N/A")}</span>
                  </div>
                  <div class="compare-row">
                    <span class="compare-lbl">Found on Card:</span>
                    <span class="compare-val mono">${escapeHtml(f.ocr_text || "N/A")}</span>
                  </div>
                  ${f.diff ? `<div class="compare-diff-tag">${escapeHtml(f.diff)}</div>` : ""}
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    `;

    auditModal.style.display = "flex";

    document.getElementById("btnLoadToLive").addEventListener("click", () => {
      auditModal.style.display = "none";
      navLiveTab.click();
      const liveData = {
        record_id: rec.id,
        audit: rec.audit_json,
        images: {
          front_annotated: null,
          back_annotated: null,
        },
        crops: {},
        meta: {
          has_back_document: Boolean(rec.has_back_document),
        },
      };
      renderResults(liveData);
      showToast(`Loaded record ${rec.id} in live view.`, "success");
    });
  }

  btnModalClose.addEventListener("click", () => {
    auditModal.style.display = "none";
  });

  auditModal.addEventListener("click", (e) => {
    if (e.target === auditModal) {
      auditModal.style.display = "none";
    }
  });

  // Search & Filter Interactions
  recordsSearchInput.addEventListener("input", () => {
    if (recordsSearchInput.value.length > 0) {
      btnSearchClear.style.display = "block";
    } else {
      btnSearchClear.style.display = "none";
    }
  });

  btnSearchClear.addEventListener("click", () => {
    recordsSearchInput.value = "";
    btnSearchClear.style.display = "none";
    loadRecords();
  });

  recordsSearchInput.addEventListener("input", debounce(loadRecords, 300));
  recordsTierFilter.addEventListener("change", loadRecords);
  refreshRecordsBtn.addEventListener("click", () => {
    loadRecords();
    loadStorageStats();
    showToast("🔄 Records list refreshed.", "info");
  });

  // Copy JSON Data
  copyJsonBtn.addEventListener("click", () => {
    if (jsonOutput.textContent) {
      navigator.clipboard.writeText(jsonOutput.textContent).then(() => {
        showToast("📋 Summary data copied to clipboard!", "success");
      });
    }
  });

  // ---------------------------------------------------------------------------
  // Toast Notifications
  // ---------------------------------------------------------------------------

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast-item ${type === "success" ? "toast-success" : type === "error" ? "toast-error" : ""}`;
    toast.textContent = message;

    toastHub.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(20px) scale(0.9)";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // ---------------------------------------------------------------------------
  // Helper Utilities
  // ---------------------------------------------------------------------------

  function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Initial load
  loadStorageStats();
});
