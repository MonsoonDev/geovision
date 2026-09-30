const USER = "#6d28d9";
const GRAPH = "#0f766e";

const NOTES = {
  pan: "",
  point: "Click to place a point. Drag a point to move it.",
  segment: "Click the two ends of a segment.",
  polygon: "Click each corner, then click the first point to close.",
  circle: "Click the center, then a point on the circle.",
  sketch: "Drag to sketch.",
  erase: "Click a shape to remove it.",
};

export function initDraw({ state, svg, view3d, hint, gfx, clientToMath, draw2d, render }) {
  const row = document.querySelector("#tool-row");
  const form = document.querySelector("#graph-form");
  let shape = null;
  let work = Promise.resolve();

  function enqueue(task) {
    const job = work.then(task);
    work = job.catch(() => {});
    return job;
  }

  function fmt(value) {
    return String(Math.round(Number(value) * 10000) / 10000);
  }

  function is3d() {
    return !!(state.scene && state.scene.view && state.scene.view.mode === "3d");
  }

  function nextId() {
    let n = 0;
    for (const obj of (state.scene && state.scene.objects) || []) {
      const match = /^u(\d+)$/.exec(obj.id);
      if (match) n = Math.max(n, Number(match[1]));
    }
    return `u${n + 1}`;
  }

  function eventToMath(event) {
    if (!is3d()) return clientToMath(event.clientX, event.clientY, state.bounds);
    if (!gfx.ready) return null;
    const rect = view3d.getBoundingClientRect();
    const THREE = gfx.THREE;
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, gfx.camera);
    const hit = new THREE.Vector3();
    if (!raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit)) return null;
    return [hit.x, hit.z, 0];
  }

  function mathToClient(point) {
    if (is3d() && gfx.ready) {
      const rect = view3d.getBoundingClientRect();
      const vector = new gfx.THREE.Vector3(point[0], point[2] || 0, point[1]).project(gfx.camera);
      return [rect.left + (vector.x + 1) * 0.5 * rect.width, rect.top + (1 - vector.y) * 0.5 * rect.height];
    }
    const bounds = state.bounds;
    const rect = svg.getBoundingClientRect();
    const w = bounds.maxX - bounds.minX;
    const h = bounds.maxY - bounds.minY;
    const scale = Math.min(rect.width / w, rect.height / h);
    const padX = (rect.width - w * scale) / 2;
    const padY = (rect.height - h * scale) / 2;
    return [
      rect.left + padX + (point[0] - bounds.minX) * scale,
      rect.top + padY + (bounds.maxY - point[1]) * scale,
    ];
  }

  function snapPoint(event) {
    let best = null;
    let bestDistance = 14;
    for (const obj of (state.scene && state.scene.objects) || []) {
      if (obj.type !== "point" || !obj.at) continue;
      const screen = mathToClient(obj.at);
      const distance = Math.hypot(screen[0] - event.clientX, screen[1] - event.clientY);
      if (distance < bestDistance) {
        best = obj;
        bestDistance = distance;
      }
    }
    return best;
  }

  function screenDistance(px, py, a, b) {
    const abx = b[0] - a[0];
    const aby = b[1] - a[1];
    const len = abx * abx + aby * aby;
    const t = len === 0 ? 0 : Math.max(0, Math.min(1, ((px - a[0]) * abx + (py - a[1]) * aby) / len));
    return Math.hypot(px - (a[0] + abx * t), py - (a[1] + aby * t));
  }

  function chains(obj) {
    if (obj.type === "point") return obj.at ? [[obj.at]] : [];
    if (obj.a && obj.b) return [[obj.a, obj.b]];
    if (obj.points) return [obj.points];
    if (obj.paths) return obj.paths;
    if (obj.samples) return [obj.samples];
    if (obj.corners) return [obj.corners];
    return [];
  }

  function hitObject(event) {
    const point = snapPoint(event);
    if (point) return point.id;
    let best = null;
    let bestDistance = 12;
    for (const obj of (state.scene && state.scene.objects) || []) {
      if (obj.type === "point") continue;
      for (const chain of chains(obj)) {
        const screens = chain.map((at) => mathToClient(at));
        for (let i = 0; i < screens.length - 1; i++) {
          const distance = screenDistance(event.clientX, event.clientY, screens[i], screens[i + 1]);
          if (distance < bestDistance) {
            best = obj.id;
            bestDistance = distance;
          }
        }
      }
    }
    return best;
  }

  async function post(commands, fit) {
    state.suppressPoll = true;
    try {
      const response = await fetch("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ commands }),
      });
      const text = await response.text();
      if (!response.ok) {
        state.note = text.trim();
        hint.textContent = state.note;
        return false;
      }
      state.keepView = !fit;
      state.raw = text;
      state.scene = JSON.parse(text);
      state.note = NOTES[state.tool] || "";
      await render();
      return true;
    } catch {
      state.note = "Could not save the drawing.";
      hint.textContent = state.note;
      return false;
    } finally {
      state.suppressPoll = false;
    }
  }

  let posts = Promise.resolve();
  function commit(commands, fit) {
    const job = posts.then(() => post(commands, fit));
    posts = job.catch(() => false);
    return job;
  }

  async function placePoint(at, event) {
    const hit = snapPoint(event);
    if (hit) return hit.id;
    const id = nextId();
    const ok = await commit(
      `point ${id} ${fmt(at[0])} ${fmt(at[1])} ${fmt(at[2] || 0)} label=${id} color=${USER} by=user`
    );
    return ok ? id : null;
  }

  function remember(kind) {
    shape = { kind, ids: [], points: [], poly: null };
    state.draft = { points: [], cursor: null };
  }

  function clearShape() {
    shape = null;
    state.draft = null;
  }

  async function place(event) {
    const tool = state.tool;
    const at = eventToMath(event);
    if (!at) {
      state.note = is3d() ? "Click the floor grid to draw in 3D." : "Click the page to draw.";
      hint.textContent = state.note;
      return;
    }
    if (tool === "point") {
      await placePoint(at, event);
      return;
    }
    if (tool === "segment") {
      if (!shape || shape.kind !== "segment") remember("segment");
      const id = await placePoint(at, event);
      if (!id) return;
      if (!shape.ids.length) {
        shape.ids.push(id);
        shape.points.push(at);
        state.draft = { points: shape.points.slice(), cursor: at };
        if (!is3d()) draw2d(state.scene);
        return;
      }
      if (shape.ids[0] === id) return;
      const seg = nextId();
      await commit(`segment ${seg} ${shape.ids[0]} ${id} color=${USER} by=user`);
      clearShape();
      return;
    }
    if (tool === "circle") {
      if (!shape || shape.kind !== "circle") remember("circle");
      const id = await placePoint(at, event);
      if (!id) return;
      if (!shape.ids.length) {
        shape.ids.push(id);
        shape.points.push(at);
        state.draft = { points: shape.points.slice(), cursor: at };
        if (!is3d()) draw2d(state.scene);
        return;
      }
      if (shape.ids[0] === id) return;
      const circle = nextId();
      await commit(`circle ${circle} ${shape.ids[0]} ${id} color=${USER} by=user`);
      clearShape();
      return;
    }
    if (tool === "polygon") {
      if (!shape || shape.kind !== "polygon") remember("polygon");
      if (event.detail >= 2) {
        if (shape.ids.length >= 3) clearShape();
        else state.note = "A polygon needs at least 3 points.";
        hint.textContent = state.note;
        if (!is3d()) draw2d(state.scene);
        return;
      }
      const snapped = snapPoint(event);
      if (shape.ids.length >= 3 && snapped && snapped.id === shape.ids[0]) {
        clearShape();
        state.note = NOTES.polygon;
        if (!is3d()) draw2d(state.scene);
        return;
      }
      const id = await placePoint(at, event);
      if (!id || shape.ids.includes(id)) return;
      shape.ids.push(id);
      shape.points.push(at);
      if (shape.ids.length >= 3) {
        shape.poly = shape.poly || nextId();
        await commit(`polygon ${shape.poly} ${shape.ids.join(" ")} color=${USER} fill=${USER}1f by=user`);
      }
      state.draft = { points: shape.points.slice(), cursor: at, close: shape.ids.length >= 3 };
      state.note = NOTES.polygon;
      if (!is3d()) draw2d(state.scene);
    }
  }

  async function eraseAt(event) {
    const id = hitObject(event);
    if (!id) {
      state.note = "Click a point or a shape.";
      hint.textContent = state.note;
      return;
    }
    const ok = await commit(`delete ${id}`);
    if (ok) state.note = NOTES.erase;
  }

  state.onPointerDown = (event) => {
    if (!state.scene || event.button !== 0) return false;
    const tool = state.tool || "pan";
    if (tool === "pan") {
      const hit = snapPoint(event);
      if (!hit || hit.from) return false;
      state.moving = { id: hit.id, z: (hit.at && hit.at[2]) || 0 };
      state.suppressPoll = true;
      return true;
    }
    if (tool === "sketch") {
      const at = eventToMath(event);
      if (!at) return true;
      state.draft = { points: [at], cursor: null };
      state.suppressPoll = true;
      return true;
    }
    if (tool === "erase") {
      enqueue(() => eraseAt(event));
      return true;
    }
    enqueue(() => place(event));
    return true;
  };

  state.onPointerMove = (event) => {
    if (state.moving) {
      const at = eventToMath(event);
      if (!at) return true;
      const obj = ((state.scene && state.scene.objects) || []).find((item) => item.id === state.moving.id);
      if (obj) obj.at = [at[0], at[1], state.moving.z];
      if (is3d()) render();
      else draw2d(state.scene);
      return true;
    }
    if (state.tool === "sketch" && state.draft && state.suppressPoll) {
      const at = eventToMath(event);
      if (!at) return true;
      const points = state.draft.points;
      const last = points[points.length - 1];
      const screen = mathToClient(last);
      if (Math.hypot(screen[0] - event.clientX, screen[1] - event.clientY) >= 4) {
        points.push(at);
        if (!is3d()) draw2d(state.scene);
      }
      return true;
    }
    if (state.draft && state.draft.points && state.draft.points.length && !is3d()) {
      const at = eventToMath(event);
      if (at) {
        state.draft.cursor = at;
        draw2d(state.scene);
      }
      return true;
    }
    return false;
  };

  state.onPointerUp = (event) => {
    if (state.moving) {
      const obj = ((state.scene && state.scene.objects) || []).find((item) => item.id === state.moving.id);
      const moving = state.moving;
      state.moving = null;
      state.suppressPoll = false;
      if (obj) {
        enqueue(() => commit(`point ${moving.id} ${fmt(obj.at[0])} ${fmt(obj.at[1])} ${fmt(obj.at[2] || 0)}`));
      }
      return true;
    }
    if (state.tool === "sketch" && state.draft) {
      const points = state.draft.points || [];
      state.draft = null;
      state.suppressPoll = false;
      if (points.length >= 2) {
        const coords = points.map((point) => `${fmt(point[0])},${fmt(point[1])}`).join(" ");
        enqueue(() => {
          const id = nextId();
          return commit(`stroke ${id} ${coords} color=${USER} by=user`);
        });
      } else if (!is3d() && state.scene) {
        draw2d(state.scene);
      }
      return true;
    }
    return false;
  };

  state.onDouble = () => state.tool === "polygon";

  state.syncControls = () => {
    if (gfx.controls) gfx.controls.enabled = (state.tool || "pan") === "pan";
  };

  function setTool(tool) {
    state.tool = tool;
    clearShape();
    state.note = NOTES[tool] || "";
    state.syncControls();
    const drawing = tool !== "pan";
    svg.style.cursor = drawing ? "crosshair" : "";
    view3d.style.cursor = drawing ? "crosshair" : "";
    for (const button of row.querySelectorAll("button")) {
      button.setAttribute("aria-pressed", button.dataset.tool === tool ? "true" : "false");
    }
    hint.textContent = state.note || (is3d() ? "Drag to orbit." : "Drag to pan. Scroll to zoom.");
    if (state.scene && !is3d()) draw2d(state.scene);
  }

  for (const [tool, label] of [
    ["pan", "Pan"],
    ["point", "Point"],
    ["segment", "Segment"],
    ["polygon", "Polygon"],
    ["circle", "Circle"],
    ["sketch", "Sketch"],
    ["erase", "Erase"],
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.tool = tool;
    button.textContent = label;
    button.setAttribute("aria-pressed", tool === "pan" ? "true" : "false");
    button.addEventListener("click", () => setTool(tool));
    row.appendChild(button);
  }

  document.querySelector("#mode-2d").addEventListener("click", () => {
    if (!is3d()) return;
    clearShape();
    enqueue(() => commit("view 2d", true));
  });
  document.querySelector("#mode-3d").addEventListener("click", () => {
    if (is3d()) return;
    clearShape();
    enqueue(() => commit("view 3d", true));
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (is3d()) {
      state.note = "Graphs are only in the 2D view.";
      hint.textContent = state.note;
      return;
    }
    const expr = document.querySelector("#graph-expr").value.trim();
    const min = document.querySelector("#graph-min").value.trim() || "-5";
    const max = document.querySelector("#graph-max").value.trim() || "5";
    if (!expr) {
      state.note = "Type an expression in x, such as x^2.";
      hint.textContent = state.note;
      return;
    }
    enqueue(() => {
      const id = nextId();
      return commit(
        `plot ${id} ${JSON.stringify(expr)} domain=${min},${max} label=${JSON.stringify(`y=${expr}`)} color=${GRAPH} by=user`,
        true
      );
    });
  });

  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    clearShape();
    state.note = NOTES[state.tool] || "";
    hint.textContent = state.note || (is3d() ? "Drag to orbit." : "Drag to pan. Scroll to zoom.");
    if (state.scene && !is3d()) draw2d(state.scene);
  });

  for (const type of ["pointerdown", "pointermove", "pointerup"]) {
    view3d.addEventListener(
      type,
      (event) => {
        if (!is3d()) return;
        const handled =
          type === "pointerdown"
            ? state.onPointerDown(event)
            : type === "pointermove"
              ? state.onPointerMove(event)
              : state.onPointerUp(event);
        if (handled && state.tool !== "pan") {
          event.preventDefault();
          event.stopPropagation();
        }
      },
      true
    );
  }
}
