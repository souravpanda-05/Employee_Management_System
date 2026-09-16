"use strict";

const page = document.body.dataset.page;
const $ = (selector, parent = document) => parent.querySelector(selector);

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[character]);
}

function initials(name = "") {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0] || "").join("").toUpperCase() || "?";
}

function formattedDate(value) {
  if (!value) return "—";
  const safeDate = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return Number.isNaN(safeDate.valueOf()) ? "—" : safeDate.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function statusBadge(status) {
  const className = status.toLowerCase().replace(/\s+/g, "-");
  return `<span class="status status-${className}">${escapeHTML(status)}</span>`;
}

function showToast(message, type = "success") {
  const region = $(".toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type === "error" ? "error" : ""}`;
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 4400);
}

function animateNumber(element, value) {
  if (!element) return;
  const target = Number(value) || 0;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    element.textContent = target.toLocaleString();
    return;
  }
  const duration = 640;
  const startedAt = performance.now();
  function step(now) {
    const progress = Math.min((now - startedAt) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 4);
    element.textContent = Math.round(target * eased).toLocaleString();
    if (progress < 1) window.requestAnimationFrame(step);
  }
  window.requestAnimationFrame(step);
}

async function api(url, options = {}) {
  const settings = { ...options, headers: { ...(options.headers || {}) } };
  if (options.body && !settings.headers["Content-Type"]) settings.headers["Content-Type"] = "application/json";
  const response = await fetch(url, settings);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : { message: "Unexpected server response." };
  if (response.status === 401 && page !== "auth") window.location.assign("/login");
  if (!response.ok) {
    const error = new Error(payload.message || "Something went wrong.");
    error.payload = payload;
    throw error;
  }
  return payload;
}

function clearFormErrors(form) {
  form.querySelectorAll(".invalid").forEach(field => field.classList.remove("invalid"));
  form.querySelectorAll(".field-error").forEach(field => { field.textContent = ""; });
}

function showFormErrors(form, errors = {}) {
  clearFormErrors(form);
  Object.entries(errors).forEach(([name, message]) => {
    const field = form.elements[name];
    if (!field) return;
    field.classList.add("invalid");
    const errorBox = field.closest("label")?.querySelector(".field-error");
    if (errorBox) errorBox.textContent = message;
  });
}

function setButtonBusy(button, busy, label) {
  if (!button) return;
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.label;
}

function initNavigation() {
  const sidebar = $("#sidebar");
  const menuButton = $("#menuButton");
  menuButton?.addEventListener("click", () => sidebar?.classList.toggle("open"));
  document.addEventListener("click", event => {
    if (sidebar?.classList.contains("open") && !sidebar.contains(event.target) && !menuButton?.contains(event.target)) sidebar.classList.remove("open");
  });
  $("#logoutButton")?.addEventListener("click", async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* still clear client route */ }
    window.location.assign("/login");
  });
}

function initAuth() {
  const loginView = $("#loginView");
  const signupView = $("#signupView");
  document.querySelectorAll("[data-auth-mode]").forEach(button => button.addEventListener("click", () => {
    const signupMode = button.dataset.authMode === "signup";
    loginView.hidden = signupMode;
    signupView.hidden = !signupMode;
    clearFormErrors(signupMode ? $("#signupForm") : $("#loginForm"));
  }));
  document.querySelectorAll(".toggle-password").forEach(button => button.addEventListener("click", () => {
    const input = $("input", button.parentElement);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    button.textContent = showing ? "Show" : "Hide";
    button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
  }));

  async function submitAuth(form, url) {
    clearFormErrors(form);
    const button = $("button[type='submit']", form);
    const data = Object.fromEntries(new FormData(form));
    setButtonBusy(button, true, "Please wait…");
    try {
      await api(url, { method: "POST", body: JSON.stringify(data) });
      window.location.assign("/dashboard");
    } catch (error) {
      showFormErrors(form, error.payload?.errors);
      showToast(error.message, "error");
    } finally {
      setButtonBusy(button, false);
    }
  }
  $("#loginForm")?.addEventListener("submit", event => { event.preventDefault(); submitAuth(event.currentTarget, "/api/auth/login"); });
  $("#signupForm")?.addEventListener("submit", event => { event.preventDefault(); submitAuth(event.currentTarget, "/api/auth/signup"); });
}

async function initDashboard() {
  const todayLabel = $("#todayLabel");
  if (todayLabel) todayLabel.textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
  try {
    const data = await api("/api/dashboard/stats");
    const stats = data.stats;
    animateNumber($("#totalCount"), stats.total);
    animateNumber($("#activeCount"), stats.active);
    animateNumber($("#leaveCount"), stats.on_leave);
    animateNumber($("#departmentCount"), stats.departments);
    const recent = $("#recentEmployees");
    recent.innerHTML = data.recent.length ? data.recent.map(employee => `
      <tr><td><div class="person-cell"><span class="avatar">${initials(employee.full_name)}</span><span><strong>${escapeHTML(employee.full_name)}</strong><small>${escapeHTML(employee.position)}</small></span></div></td>
      <td>${escapeHTML(employee.department)}</td><td>${statusBadge(employee.employment_status)}</td><td>${formattedDate(employee.joining_date)}</td></tr>`).join("") : `<tr><td colspan="4" class="empty-cell">No employees yet. Add your first team member.</td></tr>`;
    const max = Math.max(...data.departments.map(department => department.count), 1);
    $("#departmentList").innerHTML = data.departments.length ? data.departments.map(department => `<div class="department-row"><div class="department-meta"><span>${escapeHTML(department.department)}</span><span>${department.count} people</span></div><div class="progress"><span style="width:${(department.count / max) * 100}%"></span></div></div>`).join("") : `<p class="empty-state">Add employees to see your department split.</p>`;
  } catch (error) {
    showToast(error.message, "error");
    $("#recentEmployees").innerHTML = `<tr><td colspan="4" class="empty-cell">Unable to load dashboard data.</td></tr>`;
  }
}

function initEmployees() {
  const searchInput = $("#searchInput");
  const departmentFilter = $("#departmentFilter");
  const statusFilter = $("#statusFilter");
  const table = $("#employeesTable");
  const modal = $("#employeeModal");
  const form = $("#employeeForm");
  let currentEmployees = [];
  let searchTimer;

  function queryString() {
    const params = new URLSearchParams();
    if (searchInput.value.trim()) params.set("search", searchInput.value.trim());
    if (departmentFilter.value) params.set("department", departmentFilter.value);
    if (statusFilter.value) params.set("status", statusFilter.value);
    return params.toString();
  }

  function fillDepartments(departments) {
    const selected = departmentFilter.value;
    departmentFilter.innerHTML = `<option value="">All departments</option>${departments.map(item => `<option value="${escapeHTML(item)}">${escapeHTML(item)}</option>`).join("")}`;
    departmentFilter.value = selected;
  }

  function renderEmployees() {
    table.innerHTML = currentEmployees.length ? currentEmployees.map(employee => `
      <tr><td><div class="person-cell"><span class="avatar">${initials(employee.full_name)}</span><span><strong>${escapeHTML(employee.full_name)}</strong><small>${escapeHTML(employee.email)}</small></span></div></td>
      <td>${escapeHTML(employee.department)}</td><td>${escapeHTML(employee.position)}</td><td>${statusBadge(employee.employment_status)}</td><td>${formattedDate(employee.joining_date)}</td>
      <td><div class="action-row" style="position:relative"><button class="row-menu" data-menu="${employee.id}" type="button" aria-label="Actions for ${escapeHTML(employee.full_name)}">•••</button><div class="row-menu-menu" data-menu-panel="${employee.id}" hidden><button data-edit="${employee.id}" type="button">Edit employee</button><button class="danger" data-delete="${employee.id}" type="button">Delete employee</button></div></div></td></tr>`).join("") : `<tr><td colspan="6" class="empty-cell">No employees match these filters.</td></tr>`;
    const count = currentEmployees.length;
    $("#employeeCount").textContent = `${count} ${count === 1 ? "employee" : "employees"}`;
    $("#tableSummary").textContent = count ? `Showing ${count} ${count === 1 ? "employee" : "employees"}` : "No employees found";
  }

  async function loadEmployees() {
    table.innerHTML = `<tr><td colspan="6" class="empty-cell">Loading employees…</td></tr>`;
    try {
      const data = await api(`/api/employees${queryString() ? `?${queryString()}` : ""}`);
      currentEmployees = data.employees;
      fillDepartments(data.departments);
      renderEmployees();
    } catch (error) {
      table.innerHTML = `<tr><td colspan="6" class="empty-cell">Unable to load employees.</td></tr>`;
      showToast(error.message, "error");
    }
  }

  function closeModal() { modal.hidden = true; document.body.style.overflow = ""; }
  function openNewEmployee() {
    form.reset(); clearFormErrors(form); $("#employeeDbId").value = "";
    $("#modalTitle").textContent = "Add employee"; $("#modalEyebrow").textContent = "NEW TEAM MEMBER";
    form.elements.joining_date.value = new Date().toISOString().slice(0, 10);
    $("#saveEmployeeButton").textContent = "Save employee"; modal.hidden = false; document.body.style.overflow = "hidden";
    window.setTimeout(() => form.elements.employee_id.focus(), 30);
  }
  async function openEditEmployee(id) {
    const localEmployee = currentEmployees.find(employee => employee.id === id);
    if (!localEmployee) return;
    form.reset(); clearFormErrors(form);
    $("#employeeDbId").value = id; $("#modalTitle").textContent = "Edit employee"; $("#modalEyebrow").textContent = "UPDATE TEAM MEMBER"; $("#saveEmployeeButton").textContent = "Save changes";
    Object.entries(localEmployee).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = key === "joining_date" ? String(value).slice(0, 10) : value; });
    modal.hidden = false; document.body.style.overflow = "hidden";
    window.setTimeout(() => form.elements.full_name.focus(), 30);
  }
  async function deleteEmployee(id) {
    const employee = currentEmployees.find(item => item.id === id);
    if (!employee || !window.confirm(`Delete ${employee.full_name}? This action cannot be undone.`)) return;
    try { const result = await api(`/api/employees/${id}`, { method: "DELETE" }); showToast(result.message); loadEmployees(); } catch (error) { showToast(error.message, "error"); }
  }

  $("#addEmployeeButton").addEventListener("click", openNewEmployee);
  document.querySelectorAll("[data-close-modal]").forEach(button => button.addEventListener("click", closeModal));
  modal.addEventListener("click", event => { if (event.target === modal) closeModal(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && !modal.hidden) closeModal(); });
  [searchInput, departmentFilter, statusFilter].forEach(control => control.addEventListener("input", () => {
    clearTimeout(searchTimer); searchTimer = window.setTimeout(loadEmployees, control === searchInput ? 260 : 0);
  }));
  $("#exportButton").addEventListener("click", () => { window.location.assign(`/api/employees/export.csv${queryString() ? `?${queryString()}` : ""}`); });
  table.addEventListener("click", event => {
    const menuButton = event.target.closest("[data-menu]");
    const editButton = event.target.closest("[data-edit]");
    const deleteButton = event.target.closest("[data-delete]");
    if (menuButton) {
      document.querySelectorAll("[data-menu-panel]").forEach(panel => { if (panel.dataset.menuPanel !== menuButton.dataset.menu) panel.hidden = true; });
      const panel = document.querySelector(`[data-menu-panel="${menuButton.dataset.menu}"]`); panel.hidden = !panel.hidden;
    }
    if (editButton) openEditEmployee(Number(editButton.dataset.edit));
    if (deleteButton) deleteEmployee(Number(deleteButton.dataset.delete));
  });
  document.addEventListener("click", event => { if (!event.target.closest(".action-row")) document.querySelectorAll("[data-menu-panel]").forEach(panel => panel.hidden = true); });
  form.addEventListener("submit", async event => {
    event.preventDefault(); clearFormErrors(form);
    const id = $("#employeeDbId").value;
    const data = Object.fromEntries(new FormData(form)); delete data.id;
    const saveButton = $("#saveEmployeeButton"); setButtonBusy(saveButton, true, id ? "Saving…" : "Adding…");
    try {
      const result = await api(id ? `/api/employees/${id}` : "/api/employees", { method: id ? "PUT" : "POST", body: JSON.stringify(data) });
      closeModal(); showToast(result.message); loadEmployees();
    } catch (error) { showFormErrors(form, error.payload?.errors); showToast(error.message, "error"); }
    finally { setButtonBusy(saveButton, false); }
  });
  loadEmployees();
}

initNavigation();
if (page === "auth") initAuth();
if (page === "dashboard") initDashboard();
if (page === "employees") initEmployees();
