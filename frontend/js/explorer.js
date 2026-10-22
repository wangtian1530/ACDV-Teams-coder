const Explorer = {
  tree: [],
  expanded: new Set(),
  currentProject: null,

  async loadProjects() {
    const list = document.getElementById("projectList");
    try {
      const projects = await API.listProjects();
      list.innerHTML = "";
      if (!projects || !projects.length) {
        list.innerHTML = '<li class="project-empty">No projects yet</li>';
        return;
      }
      projects.forEach(p => {
        const li = document.createElement("li");
        li.className = "project-item" + (p.name === this.currentProject ? " active" : "");
        li.innerHTML = `<span>📦</span><span>${p.name}</span>`;
        li.onclick = () => this.openProject(p.name);

        const dlBtn = document.createElement("button");
        dlBtn.className = "icon-btn small project-dl";
        dlBtn.title = "Download project as ZIP";
        dlBtn.textContent = "⬇";
        dlBtn.style.marginLeft = "auto";
        dlBtn.onclick = (e) => {
          e.stopPropagation();
          if (window.App && typeof App.exportProject === "function") {
            App.exportProject(p.name);
          }
        };
        ["touchstart", "touchend", "mousedown", "mouseup"].forEach(evt => {
          dlBtn.addEventListener(evt, (e) => e.stopPropagation());
        });
        li.appendChild(dlBtn);

        let timer;
        li.addEventListener("touchstart", () => {
          timer = setTimeout(() => {
            if (confirm(`Delete project "${p.name}"?`)) this.deleteProject(p.name);
          }, 600);
        }, { passive: true });
        li.addEventListener("touchend", () => clearTimeout(timer));
        li.addEventListener("contextmenu", (e) => {
          e.preventDefault();
          if (confirm(`Delete project "${p.name}"?`)) this.deleteProject(p.name);
        });
        list.appendChild(li);
      });
    } catch (e) {
      App.log(`✗ Load projects: ${e.message}`, "error");
    }
  },

  async openProject(name) {
    this.currentProject = name;
    this.expanded.clear();
    document.getElementById("currentProjectName").textContent = name;
    App.log(`Opened project: ${name}`);
    App.switchTab("explorer");
    if (window.innerWidth < 768) {
      document.getElementById("sidebar").classList.add("open");
    }
    await this.refreshTree();
    this.loadProjects();
  },

  async refreshTree() {
    if (!this.currentProject) return;
    const treeEl = document.getElementById("fileTree");
    try {
      const res = await API.getTree(this.currentProject);
      this.tree = res.tree || [];
      treeEl.innerHTML = "";
      if (!this.tree.length) {
        treeEl.innerHTML = '<li class="project-empty">Empty project</li>';
      }
      this._renderNodes(treeEl, this.tree, "");
    } catch (e) {
      App.log(`✗ Load tree: ${e.message}`, "error");
    }
  },

  _renderNodes(parentEl, nodes, prefix) {
    nodes.forEach(node => {
      const fullPath = prefix ? `${prefix}/${node.name}` : node.name;
      const li = document.createElement("li");
      const item = document.createElement("div");
      item.className = "file-item" + (node.type === "dir" ? " dir" : "");
      const icon = node.type === "dir"
        ? (this.expanded.has(fullPath) ? "▾" : "▸")
        : "◦";
      item.innerHTML = `<span class="chev">${icon}</span><span>${node.name}</span>`;

      if (node.type === "file") {
        const ext = (node.name.split(".").pop() || "").toLowerCase();
        if (["py", "js", "sh", "bash"].includes(ext)) {
          const runBtn = document.createElement("button");
          runBtn.className = "icon-btn small run-inline";
          runBtn.title = "Run file";
          runBtn.textContent = "▶";
          runBtn.onclick = (ev) => {
            ev.stopPropagation();
            App.runFile(this.currentProject, fullPath);
          };
          item.appendChild(runBtn);
        }
      }

      item.onclick = async () => {
        if (node.type === "dir") {
          if (this.expanded.has(fullPath)) this.expanded.delete(fullPath);
          else this.expanded.add(fullPath);
          await this.refreshTree();
        } else {
          await App.openFile(this.currentProject, fullPath);
        }
      };

      let timer;
      item.addEventListener("touchstart", () => {
        timer = setTimeout(() => this._showContext(node, fullPath), 600);
      }, { passive: true });
      item.addEventListener("touchend", () => clearTimeout(timer));
      item.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        this._showContext(node, fullPath);
      });

      li.appendChild(item);

      if (node.type === "dir" && this.expanded.has(fullPath) && node.children?.length) {
        const sub = document.createElement("ul");
        sub.className = "file-children";
        this._renderNodes(sub, node.children, fullPath);
        li.appendChild(sub);
      }
      parentEl.appendChild(li);
    });
  },

  _showContext(node, fullPath) {
    const ext = (node.name.split(".").pop() || "").toLowerCase();
    const canRun = node.type === "file" && ["py", "js", "sh", "bash"].includes(ext);
    const hint = canRun
      ? `"${fullPath}"\n\nGõ "r" đổi tên, "d" xoá, "x" chạy file`
      : `"${fullPath}"\n\nGõ "r" đổi tên, "d" xoá`;
    const action = prompt(hint, "");
    if (action === "r") {
      const newPath = prompt("Tên/đường dẫn mới:", fullPath);
      if (newPath && newPath !== fullPath) this._rename(fullPath, newPath);
    } else if (action === "d") {
      if (confirm(`Xoá "${fullPath}"?`)) this._delete(fullPath);
    } else if (action === "x" && canRun) {
      App.runFile(this.currentProject, fullPath);
    }
  },

  async _rename(oldPath, newPath) {
    try {
      await API.renameFile(this.currentProject, oldPath, newPath);
      App.log(`✓ Renamed ${oldPath} → ${newPath}`, "success");
      await this.refreshTree();
    } catch (e) {
      App.log(`✗ Rename: ${e.message}`, "error");
    }
  },

  async _delete(path) {
    try {
      await API.deleteFile(this.currentProject, path);
      App.log(`✓ Deleted ${path}`, "success");
      await this.refreshTree();
    } catch (e) {
      App.log(`✗ Delete: ${e.message}`, "error");
    }
  },

  async deleteProject(name) {
    try {
      await API.deleteProject(name);
      if (this.currentProject === name) {
        this.currentProject = null;
        document.getElementById("currentProjectName").textContent = "No project";
        document.getElementById("fileTree").innerHTML = "";
      }
      App.log(`✓ Deleted project ${name}`, "success");
      await this.loadProjects();
    } catch (e) {
      App.log(`✗ Delete project: ${e.message}`, "error");
    }
  },

  promptNewFile() {
    if (!this.currentProject) { App.log("Open a project first", "error"); return; }
    App.prompt("New File", "vd: src/utils.py").then(async (path) => {
      if (!path) return;
      try {
        await API.createFile(this.currentProject, path);
        App.log(`✓ Created ${path}`, "success");
        await this.refreshTree();
      } catch (e) { App.log(`✗ ${e.message}`, "error"); }
    });
  },

  promptNewFolder() {
    if (!this.currentProject) { App.log("Open a project first", "error"); return; }
    App.prompt("New Folder", "vd: src/components").then(async (path) => {
      if (!path) return;
      try {
        await API.createFolder(this.currentProject, path);
        App.log(`✓ Created folder ${path}`, "success");
        await this.refreshTree();
      } catch (e) { App.log(`✗ ${e.message}`, "error"); }
    });
  },
};