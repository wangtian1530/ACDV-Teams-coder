const API = {
  async request(path, method = "GET", body = null) {
    const opts = { method, headers: {} };
    if (body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }
    if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
    if (data && typeof data === "object" && data.ok === false) {
      throw new Error(data.error || "Request failed");
    }
    return data;
  },

  listProjects: () => API.request("/api/projects"),
  createProject: (name, language) =>
    API.request("/api/projects/create", "POST", { name, language }),
  uploadProject: (name, zipBase64) =>
    API.request("/api/projects/upload", "POST", { name, zip_base64: zipBase64 }),
  deleteProject: (name) =>
    API.request("/api/projects/delete", "POST", { name }),
  // ⭐ NEW: export project ZIP
  exportProject: (name) =>
    API.request("/api/projects/export", "POST", { name }),
  getTree: (project) =>
    API.request("/api/projects/tree", "POST", { project }),

  readFile: (project, path) =>
    API.request("/api/projects/file/read", "POST", { project, path }),
  writeFile: (project, path, content) =>
    API.request("/api/projects/file/write", "POST", { project, path, content }),
  createFile: (project, path) =>
    API.request("/api/projects/file/create", "POST", { project, path }),
  createFolder: (project, path) =>
    API.request("/api/projects/folder/create", "POST", { project, path }),
  deleteFile: (project, path) =>
    API.request("/api/projects/file/delete", "POST", { project, path }),
  renameFile: (project, old_path, new_path) =>
    API.request("/api/projects/file/rename", "POST", { project, old_path, new_path }),

  listModules: () => API.request("/api/modules"),
  installModule: (zipBase64) =>
    API.request("/api/modules/install", "POST", { zip_base64: zipBase64 }),
  uninstallModule: (name) =>
    API.request("/api/modules/uninstall", "POST", { name }),
  reloadModule: (name) =>
    API.request("/api/modules/reload", "POST", { name }),
  // ⭐ NEW: export module ZIP
  exportModule: (name) =>
    API.request("/api/modules/export", "POST", { name }),

  runFile: (project, path) =>
    API.request("/api/projects/run", "POST", { project, path }),
  // ⭐ v1.2.1: force param
  stopRun: (force = false) =>
    API.request("/api/projects/run/stop", "POST", { force }),
  runStatus: () => API.request("/api/projects/run/status", "GET"),

  listLogs: (project) =>
    API.request("/api/projects/logs/list", "POST", { project }),
  readLog: (name) =>
    API.request("/api/projects/logs/read", "POST", { name }),
  deleteLog: (name) =>
    API.request("/api/projects/logs/delete", "POST", { name }),
};