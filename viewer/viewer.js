const SVG_NS = "http://www.w3.org/2000/svg";
const svg = document.querySelector("#view2d");
const view3d = document.querySelector("#view3d");
const hint = document.querySelector("#hint");

const state = {
  raw: "",
  scene: null,
  step: Infinity,
  maxStep: 0,
  bounds: { minX: -5, minY: -5, maxX: 5, maxY: 5 },
  geomKey: "",
  camKey: "",
  drag: null,
  tool: "pan",
  note: "",
  draft: null,
  keepView: false,
  suppressPoll: false,
};

const gfx = {
  ready: false,
  failed: false,
  THREE: null,
  scene: null,
  content: null,
  camera: null,
  controls: null,
  renderer: null,
  labels: null,
};

document.querySelector("#step").addEventListener("input", (event) => {
  state.step = Number(event.target.value);
  if (state.scene) render();
});

svg.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  if (state.onPointerDown && state.onPointerDown(event)) return;
  state.drag = { x: event.clientX, y: event.clientY, bounds: { ...state.bounds } };
  svg.classList.add("dragging");
  svg.setPointerCapture(event.pointerId);
});

svg.addEventListener("pointermove", (event) => {
  if (state.onPointerMove && state.onPointerMove(event)) return;
  if (!state.drag) return;
  const start = clientToMath(state.drag.x, state.drag.y, state.drag.bounds);
  const now = clientToMath(event.clientX, event.clientY, state.drag.bounds);
  const dx = now[0] - start[0];
  const dy = now[1] - start[1];
  const b = state.drag.bounds;
  state.bounds = {
    minX: b.minX - dx,
    maxX: b.maxX - dx,
    minY: b.minY - dy,
    maxY: b.maxY - dy,
  };
  draw2d(state.scene);
});

svg.addEventListener("pointerup", (event) => {
  if (state.onPointerUp && state.onPointerUp(event)) {
    state.drag = null;
    svg.classList.remove("dragging");
    return;
  }
  state.drag = null;
  svg.classList.remove("dragging");
});

svg.addEventListener("pointercancel", (event) => {
  if (state.onPointerUp) state.onPointerUp(event);
  state.drag = null;
  svg.classList.remove("dragging");
});

svg.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    const [mx, my] = clientToMath(event.clientX, event.clientY, state.bounds);
    const factor = event.deltaY > 0 ? 1.1 : 0.9;
    const b = state.bounds;
    state.bounds = {
      minX: mx - (mx - b.minX) * factor,
      maxX: mx + (b.maxX - mx) * factor,
      minY: my - (my - b.minY) * factor,
      maxY: my + (b.maxY - my) * factor,
    };
    draw2d(state.scene);
  },
  { passive: false }
);

svg.addEventListener("dblclick", (event) => {
  if (state.onDouble && state.onDouble(event)) return;
  if (!state.scene) return;
  state.bounds = computeBounds(state.scene);
  draw2d(state.scene);
});

function clientToMath(clientX, clientY, bounds) {
  const rect = svg.getBoundingClientRect();
  const w = bounds.maxX - bounds.minX;
  const h = bounds.maxY - bounds.minY;
  const scale = Math.min(rect.width / w, rect.height / h);
  const padX = (rect.width - w * scale) / 2;
  const padY = (rect.height - h * scale) / 2;
  const u = (clientX - rect.left - padX) / scale;
  const v = (clientY - rect.top - padY) / scale;
  return [bounds.minX + u, bounds.maxY - v];
}

function gridStep(span) {
  const raw = span / 8;
  if (!(raw > 0)) return 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  for (const multiplier of [1, 2, 5, 10]) {
    if (raw <= multiplier * mag) return multiplier * mag;
  }
  return 10 * mag;
}

function objectPoints(obj) {
  switch (obj.type) {
    case "point":
    case "label":
      return obj.at ? [obj.at] : [];
    case "segment":
    case "line":
    case "ray":
    case "vector":
      return [obj.a, obj.b];
    case "circle":
      return obj.samples || [];
    case "sphere": {
      const c = obj.center;
      const r = obj.radius;
      return [
        [c[0] - r, c[1] - r, c[2] - r],
        [c[0] + r, c[1] + r, c[2] + r],
      ];
    }
    case "polygon":
    case "polyline":
    case "angle":
    case "right_angle":
      return obj.points || [];
    case "curve":
      return (obj.paths || []).flat();
    case "plane":
      return obj.corners || [];
    case "polyhedron":
      return obj.vertices || [];
    default:
      return [];
  }
}

function computeBounds(scene) {
  const given = scene.view && scene.view.bounds;
  if (given && given.length === 4 && given[2] > given[0] && given[3] > given[1]) {
    return { minX: given[0], minY: given[1], maxX: given[2], maxY: given[3] };
  }
  const points = [];
  for (const obj of scene.objects || []) points.push(...objectPoints(obj));
  if (!points.length) return { minX: -5, minY: -5, maxX: 5, maxY: 5 };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const point of points) {
    minX = Math.min(minX, point[0]);
    maxX = Math.max(maxX, point[0]);
    minY = Math.min(minY, point[1]);
    maxY = Math.max(maxY, point[1]);
  }
  const padX = (maxX - minX) * 0.2 + 1;
  const padY = (maxY - minY) * 0.2 + 1;
  return { minX: minX - padX, minY: minY - padY, maxX: maxX + padX, maxY: maxY + padY };
}

function geometryKey(scene) {
  return JSON.stringify(
    (scene.objects || []).map((obj) => {
      const copy = { ...obj };
      delete copy.style;
      return copy;
    })
  );
}

function shown(obj) {
  return (obj.step || 0) <= state.step;
}

function syncSteps(scene) {
  const maxStep = (scene.objects || []).reduce((max, obj) => Math.max(max, obj.step || 0), 0);
  const names = new Map((scene.steps || []).map((step) => [step.index, step.name]));
  const box = document.querySelector("#stepbox");
  const input = document.querySelector("#step");
  const label = document.querySelector("#step-label");
  if (maxStep <= 0 && names.size === 0) {
    box.hidden = true;
    state.step = Infinity;
  } else {
    box.hidden = false;
    const wasAtEnd = state.step === Infinity || state.step >= state.maxStep;
    state.step = wasAtEnd ? maxStep : Math.min(state.step, maxStep);
    input.max = String(maxStep);
    input.value = String(state.step);
    const name = names.get(state.step);
    label.textContent = name ? `Step ${state.step}: ${name}` : `Step ${state.step}`;
  }
  state.maxStep = maxStep;
}

function renderList(scene) {
  const list = document.querySelector("#list");
  list.replaceChildren();
  const objects = (scene.objects || []).filter(shown);
  if (!objects.length) {
    const item = document.createElement("li");
    item.className = "empty";
    item.textContent = "Nothing in this step.";
    list.appendChild(item);
    return;
  }
  for (const obj of objects) {
    const item = document.createElement("li");
    item.className = "obj";
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    if (obj.style && obj.style.highlight) swatch.classList.add("on");
    swatch.style.background = (obj.style && obj.style.color) || "#1d4ed8";
    const id = document.createElement("span");
    id.className = "id";
    const label = obj.style && obj.style.label;
    id.textContent = label && label !== obj.id ? `${obj.id}  ${label}` : obj.id;
    const kind = document.createElement("span");
    kind.className = "kind";
    const mode = scene.view && scene.view.mode === "3d" ? "3d" : "2d";
    kind.textContent = obj.type === "curve" && obj.expr ? `y=${obj.expr}` : obj.type;
    if (obj.author === "user") kind.textContent += " · you";
    if (obj.type === "curve" && mode === "3d") kind.textContent += " · 2D only";
    item.append(swatch, id, kind);
    list.appendChild(item);
  }
}

async function render() {
  const scene = state.scene;
  if (!scene) return;
  const title = scene.title || "Untitled";
  document.querySelector("#title").textContent = title;
  document.title = title === "Untitled" ? "GeoVision" : `${title} — GeoVision`;
  syncSteps(scene);
  renderList(scene);
  const mode = scene.view && scene.view.mode === "3d" ? "3d" : "2d";
  document.body.classList.toggle("is-3d", mode === "3d");
  document.querySelector("#mode-2d").setAttribute("aria-pressed", mode === "2d" ? "true" : "false");
  document.querySelector("#mode-3d").setAttribute("aria-pressed", mode === "3d" ? "true" : "false");
  document.querySelector("#graph-form").hidden = mode === "3d";
  document.querySelector("#graph-note").hidden = mode !== "3d";
  svg.hidden = mode === "3d";
  view3d.hidden = mode !== "3d";
  const key = geometryKey(scene);
  if (key !== state.geomKey) {
    state.geomKey = key;
    if (!state.keepView) state.bounds = computeBounds(scene);
  }
  state.keepView = false;
  hint.textContent = state.note || (mode === "3d" ? "Drag to orbit." : "Drag to pan. Scroll to zoom.");
  if (mode === "2d") {
    draw2d(scene);
  } else {
    try {
      await draw3d(scene);
    } catch (error) {
      gfx.failed = true;
      hint.textContent = "The 3D view could not load Three.js.";
      console.error(error);
    }
  }
}

function draw2d(scene) {
  if (!scene) return;
  const bounds = state.bounds;
  const spanX = Math.max(bounds.maxX - bounds.minX, 1e-6);
  const spanY = Math.max(bounds.maxY - bounds.minY, 1e-6);
  svg.setAttribute("viewBox", `${bounds.minX} ${-bounds.maxY} ${spanX} ${spanY}`);
  svg.replaceChildren();
  svg.style.background = (scene.view && scene.view.background) || "#f4f0e6";
  const unit = unitsPerPx(bounds);
  if (scene.view && scene.view.grid !== false) drawGrid(bounds, unit);
  if (!scene.view || scene.view.axes !== false) drawAxes(bounds, unit);
  const objects = (scene.objects || []).filter(shown);
  objects.sort((a, b) => {
    const ha = a.style && a.style.highlight ? 1 : 0;
    const hb = b.style && b.style.highlight ? 1 : 0;
    return ha - hb || layer(a) - layer(b);
  });
  for (const obj of objects) drawObject(obj, bounds, unit);
  drawDraft(unit);
}

function unitsPerPx(bounds) {
  const rect = svg.getBoundingClientRect();
  const w = Math.max(rect.width, 1);
  const h = Math.max(rect.height, 1);
  return Math.max((bounds.maxX - bounds.minX) / w, (bounds.maxY - bounds.minY) / h);
}

function layer(obj) {
  if (["plane", "polyhedron", "sphere", "polygon"].includes(obj.type)) return 0;
  if (obj.type === "point") return 3;
  if (obj.type === "label") return 4;
  return 1;
}

function drawGrid(bounds, unit) {
  const step = gridStep(Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY));
  if (!(step > 0)) return;
  let guard = 0;
  for (let x = Math.ceil(bounds.minX / step) * step; x <= bounds.maxX + step * 0.01 && guard < 80; x += step) {
    svg.appendChild(line([x, bounds.minY], [x, bounds.maxY], "#e4dcd0", 1, unit));
    guard += 1;
  }
  guard = 0;
  for (let y = Math.ceil(bounds.minY / step) * step; y <= bounds.maxY + step * 0.01 && guard < 80; y += step) {
    svg.appendChild(line([bounds.minX, y], [bounds.maxX, y], "#e4dcd0", 1, unit));
    guard += 1;
  }
}

function drawAxes(bounds, unit) {
  if (bounds.minY <= 0 && bounds.maxY >= 0) {
    svg.appendChild(line([bounds.minX, 0], [bounds.maxX, 0], "#a8a29e", 1.25, unit));
  }
  if (bounds.minX <= 0 && bounds.maxX >= 0) {
    svg.appendChild(line([0, bounds.minY], [0, bounds.maxY], "#a8a29e", 1.25, unit));
  }
}

function drawObject(obj, bounds, unit) {
  const style = obj.style || {};
  const haloTypes = ["segment", "line", "ray", "vector", "polyline", "polygon", "circle", "curve", "angle", "right_angle"];
  if (style.highlight && haloTypes.includes(obj.type) && !style._halo) {
    drawObject(
      {
        ...obj,
        style: {
          ...style,
          highlight: false,
          label: "",
          color: "#d97706",
          width: (style.width || 2) + 6,
          opacity: 0.22,
          _halo: true,
        },
      },
      bounds,
      unit
    );
  }
  const color = style.highlight ? "#d97706" : style.color || "#1d4ed8";
  let width = style.width || 2;
  if (style.highlight) width += 1.5;
  const dash = !!style.dash;
  if (obj.type === "point") {
    if (style.highlight) svg.appendChild(dot(obj.at, "#d97706", 9, unit, 0.28));
    svg.appendChild(dot(obj.at, color, style.highlight ? 5.5 : 4.5, unit, style.opacity));
  } else if (obj.type === "segment" || obj.type === "line" || obj.type === "ray") {
    const clipped = clipLinear(obj.type, obj.a, obj.b, bounds);
    if (clipped) svg.appendChild(line(clipped[0], clipped[1], color, width, unit, dash, style.opacity));
  } else if (obj.type === "vector") {
    const clipped = clipLinear("segment", obj.a, obj.b, bounds);
    if (clipped) svg.appendChild(line(clipped[0], clipped[1], color, width, unit, dash, style.opacity));
    if (obj.head) svg.appendChild(path(obj.head, color, width, unit, dash, style.opacity, false));
  } else if (obj.type === "polyline" || obj.type === "angle" || obj.type === "right_angle") {
    svg.appendChild(path(obj.points || [], color, width, unit, dash, style.opacity, false));
  } else if (obj.type === "curve") {
    for (const curve of obj.paths || []) svg.appendChild(path(curve, color, width, unit, dash, style.opacity, false));
  } else if (obj.type === "polygon") {
    svg.appendChild(path(obj.points || [], color, width, unit, dash, style.opacity, true, style.fill));
  } else if (obj.type === "circle") {
    drawCircle(obj, color, width, unit, dash, style);
  } else if (obj.type === "sphere") {
    svg.appendChild(circleXY(obj.center, obj.radius, color, width, unit, dash, style));
  } else if (obj.type === "plane") {
    svg.appendChild(path(obj.corners || [], color, width, unit, dash, style.opacity, true, style.fill));
  } else if (obj.type === "polyhedron") {
    drawEdges(obj, color, width, unit, dash, style.opacity);
  }
  const label = style.label || (obj.type === "label" ? obj.text : "");
  if (label) {
    const anchor = labelAnchor(obj);
    if (anchor) svg.appendChild(text(anchor, label, unit, obj.type === "point"));
  }
}

function drawCircle(obj, color, width, unit, dash, style) {
  const normal = obj.normal || [0, 0, 1];
  if (Math.abs(normal[0]) < 1e-6 && Math.abs(normal[1]) < 1e-6) {
    svg.appendChild(circleXY(obj.center, obj.radius, color, width, unit, dash, style));
  } else {
    svg.appendChild(path(obj.samples || [], color, width, unit, dash, style.opacity, true, style.fill));
  }
}

function drawEdges(obj, color, width, unit, dash, opacity) {
  const verts = obj.vertices || [];
  const seen = new Set();
  for (const face of obj.faces || []) {
    for (let i = 0; i < face.length; i++) {
      const a = face[i];
      const b = face[(i + 1) % face.length];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key) || !verts[a] || !verts[b]) continue;
      seen.add(key);
      svg.appendChild(line(verts[a], verts[b], color, width, unit, dash, opacity));
    }
  }
}

function drawDraft(unit) {
  const draft = state.draft;
  if (!draft) return;
  const color = "#6d28d9";
  if (draft.points && draft.points.length >= 2) {
    svg.appendChild(path(draft.points, color, 2, unit, true, 0.85, !!draft.close));
  }
  for (const point of draft.points || []) svg.appendChild(dot(point, color, 4.5, unit));
  const last = draft.points && draft.points[draft.points.length - 1];
  if (last && draft.cursor) svg.appendChild(line(last, draft.cursor, color, 1.5, unit, true, 0.7));
}

function labelAnchor(obj) {
  if (obj.labelAt) return obj.labelAt;
  if (obj.paths && obj.paths[0] && obj.paths[0].length) return obj.paths[0][Math.floor(obj.paths[0].length / 2)];
  if (obj.at) return obj.at;
  if (obj.center) return obj.center;
  const points = obj.points || obj.corners || obj.vertices;
  if (points && points.length) {
    const at = [0, 0, 0];
    for (const point of points) {
      at[0] += point[0];
      at[1] += point[1];
      at[2] += point[2] || 0;
    }
    return at.map((value) => value / points.length);
  }
  if (obj.a && obj.b) {
    return [(obj.a[0] + obj.b[0]) / 2, (obj.a[1] + obj.b[1]) / 2, ((obj.a[2] || 0) + (obj.b[2] || 0)) / 2];
  }
  return null;
}

function el(name, attrs) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function line(a, b, color, width, unit, dash = false, opacity = null) {
  return el("line", {
    x1: a[0],
    y1: -a[1],
    x2: b[0],
    y2: -b[1],
    ...strokeAttrs(color, width, unit, dash, opacity),
  });
}

function dot(at, color, radiusPx, unit, opacity) {
  const attrs = { cx: at[0], cy: -at[1], r: radiusPx * unit, fill: color };
  if (opacity != null) attrs["fill-opacity"] = opacity;
  return el("circle", attrs);
}

function circleXY(center, radius, color, width, unit, dash, style) {
  const painted = paint(style.fill);
  const attrs = {
    cx: center[0],
    cy: -center[1],
    r: radius,
    ...strokeAttrs(color, width, unit, dash, style.opacity),
    fill: painted.color,
  };
  if (painted.opacity != null) attrs["fill-opacity"] = painted.opacity;
  return el("circle", attrs);
}

function path(points, color, width, unit, dash, opacity, close, fill) {
  if (!points || points.length < 2) return el("g", {});
  let d = "";
  points.forEach((point, index) => {
    d += `${index === 0 ? "M" : "L"}${point[0]} ${-point[1]} `;
  });
  if (close) d += "Z";
  const painted = paint(close ? fill : null);
  const attrs = {
    d,
    ...strokeAttrs(color, width, unit, dash, opacity),
    fill: painted.color,
  };
  if (painted.opacity != null) attrs["fill-opacity"] = painted.opacity;
  return el("path", attrs);
}

function text(at, label, unit, beside) {
  const node = el("text", {
    x: at[0],
    y: -at[1],
    dx: beside ? 8 * unit : 0,
    dy: -8 * unit,
    fill: "#1c1917",
    "font-family": "Palatino, Georgia, serif",
    "font-size": 15 * unit,
    "text-anchor": beside ? "start" : "middle",
    stroke: "#f4f0e6",
    "stroke-width": 4 * unit,
    "paint-order": "stroke",
  });
  node.textContent = label;
  return node;
}

function strokeAttrs(color, width, unit, dash, opacity) {
  const attrs = {
    stroke: color,
    "stroke-width": width,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "vector-effect": "non-scaling-stroke",
  };
  if (dash) attrs["stroke-dasharray"] = `${6 * unit} ${4 * unit}`;
  if (opacity != null) attrs["stroke-opacity"] = opacity;
  return attrs;
}

function paint(color) {
  if (!color || color === "none") return { color: "none", opacity: null };
  const hex = String(color).replace("#", "");
  if (hex.length === 8) {
    return { color: `#${hex.slice(0, 6)}`, opacity: parseInt(hex.slice(6), 16) / 255 };
  }
  return { color, opacity: null };
}

function clipLinear(kind, a, b, bounds) {
  const span = Math.hypot(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
  let start = a;
  let end = b;
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const dz = (b[2] || 0) - (a[2] || 0);
  const mag = Math.hypot(dx, dy, dz);
  if (kind === "line" || kind === "ray") {
    if (mag < 1e-12) return null;
    const scale = (span * 4) / mag;
    if (kind === "line") {
      const mx = (a[0] + b[0]) / 2;
      const my = (a[1] + b[1]) / 2;
      const mz = ((a[2] || 0) + (b[2] || 0)) / 2;
      start = [mx - dx * scale, my - dy * scale, mz - dz * scale];
      end = [mx + dx * scale, my + dy * scale, mz + dz * scale];
    } else {
      end = [a[0] + dx * scale, a[1] + dy * scale, (a[2] || 0) + dz * scale];
    }
  }
  return clipSegment(start, end, bounds);
}

function clipSegment(a, b, bounds) {
  let x0 = a[0];
  let y0 = a[1];
  let z0 = a[2] || 0;
  let x1 = b[0];
  let y1 = b[1];
  let z1 = b[2] || 0;
  const code = (x, y) => {
    let c = 0;
    if (x < bounds.minX) c |= 1;
    else if (x > bounds.maxX) c |= 2;
    if (y < bounds.minY) c |= 4;
    else if (y > bounds.maxY) c |= 8;
    return c;
  };
  let c0 = code(x0, y0);
  let c1 = code(x1, y1);
  for (let i = 0; i < 16; i++) {
    if (c0 === 0 && c1 === 0) return [[x0, y0, z0], [x1, y1, z1]];
    if (c0 & c1) return null;
    const c = c0 || c1;
    let x;
    let y;
    let z;
    if (c & 1) {
      const t = (bounds.minX - x0) / (x1 - x0);
      x = bounds.minX;
      y = y0 + t * (y1 - y0);
      z = z0 + t * (z1 - z0);
    } else if (c & 2) {
      const t = (bounds.maxX - x0) / (x1 - x0);
      x = bounds.maxX;
      y = y0 + t * (y1 - y0);
      z = z0 + t * (z1 - z0);
    } else if (c & 4) {
      const t = (bounds.minY - y0) / (y1 - y0);
      y = bounds.minY;
      x = x0 + t * (x1 - x0);
      z = z0 + t * (z1 - z0);
    } else {
      const t = (bounds.maxY - y0) / (y1 - y0);
      y = bounds.maxY;
      x = x0 + t * (x1 - x0);
      z = z0 + t * (z1 - z0);
    }
    if (c === c0) {
      x0 = x;
      y0 = y;
      z0 = z;
      c0 = code(x, y);
    } else {
      x1 = x;
      y1 = y;
      z1 = z;
      c1 = code(x, y);
    }
  }
  return null;
}

function toThree(THREE, point) {
  return new THREE.Vector3(point[0], point[2] || 0, point[1]);
}

async function draw3d(scene) {
  await ensureThree();
  if (!gfx.ready) return;
  const THREE = gfx.THREE;
  clearContent();
  const span = Math.max(
    state.bounds.maxX - state.bounds.minX,
    state.bounds.maxY - state.bounds.minY,
    4
  );
  const size = Math.max(10, Math.ceil(span));
  const grid = new THREE.GridHelper(size, size, 0xc8bfb2, 0xe4ddd2);
  gfx.content.add(grid);
  addAxes(THREE, size / 2);
  const objects = (scene.objects || []).filter((obj) => shown(obj) && obj.type !== "curve");
  for (const obj of objects) addObject3d(THREE, obj, span);
  const camKey = JSON.stringify((scene.view && scene.view.camera) || null);
  if (camKey !== state.camKey) {
    state.camKey = camKey;
    const cam = scene.view.camera;
    gfx.camera.position.copy(toThree(THREE, cam.position));
    gfx.controls.target.copy(toThree(THREE, cam.target));
    gfx.controls.update();
  }
  gfx.scene.background = new THREE.Color((scene.view && scene.view.background) || "#f4f0e6");
  resize3d();
}

function addAxes(THREE, length) {
  const axes = [
    [[length, 0, 0], 0xb4534a],
    [[0, length, 0], 0x3f7d4e],
    [[0, 0, length], 0x2f5da8],
  ];
  for (const [end, color] of axes) {
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      toThree(THREE, end),
    ]);
    gfx.content.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color })));
  }
}

function addObject3d(THREE, obj, span) {
  const style = obj.style || {};
  const color = new THREE.Color(style.highlight ? "#d97706" : style.color || "#1d4ed8");
  if (obj.type === "point") {
    const radius = span * (style.highlight ? 0.018 : 0.011);
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 16, 12),
      new THREE.MeshStandardMaterial({ color, roughness: 0.45 })
    );
    mesh.position.copy(toThree(THREE, obj.at));
    gfx.content.add(mesh);
  } else if (obj.type === "segment" || obj.type === "line" || obj.type === "ray" || obj.type === "vector") {
    const [a, b] = extend3d(obj.type === "vector" ? "segment" : obj.type, obj.a, obj.b, span);
    gfx.content.add(segment3d(THREE, a, b, color));
    if (obj.head) gfx.content.add(fanMesh(THREE, obj.head, color, 1));
  } else if (obj.type === "polyline" || obj.type === "angle" || obj.type === "right_angle") {
    gfx.content.add(strip3d(THREE, obj.points || [], color, false));
  } else if (obj.type === "curve") {
    for (const curve of obj.paths || []) gfx.content.add(strip3d(THREE, curve, color, false));
  } else if (obj.type === "polygon") {
    if (style.fill && style.fill !== "none") gfx.content.add(fanMesh(THREE, obj.points, colorFrom(style.fill, color), opacityOf(obj, style.fill)));
    gfx.content.add(strip3d(THREE, obj.points || [], color, true));
  } else if (obj.type === "circle") {
    if (style.fill && style.fill !== "none") {
      gfx.content.add(circleFill(THREE, obj, colorFrom(style.fill, color), opacityOf(obj, style.fill)));
    }
    gfx.content.add(strip3d(THREE, obj.samples || [], color, true));
  } else if (obj.type === "sphere") {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(obj.radius, 40, 28), surfaceMaterial(THREE, obj, color));
    mesh.position.copy(toThree(THREE, obj.center));
    gfx.content.add(mesh);
  } else if (obj.type === "plane") {
    gfx.content.add(fanMesh(THREE, obj.corners, colorFrom(style.fill, color), opacityOf(obj, style.fill)));
    gfx.content.add(strip3d(THREE, obj.corners || [], color, true));
  } else if (obj.type === "polyhedron") {
    gfx.content.add(polyMesh(THREE, obj, color));
    gfx.content.add(edgeMesh(THREE, obj, color));
  }
  const label = style.label || (obj.type === "label" ? obj.text : "");
  const anchor = labelAnchor(obj);
  if (label && anchor) gfx.content.add(tag(THREE, anchor, label, labelMeta(obj)));
}

function extend3d(kind, a, b, span) {
  if (kind !== "line" && kind !== "ray") return [a, b];
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const dz = (b[2] || 0) - (a[2] || 0);
  const mag = Math.hypot(dx, dy, dz) || 1;
  const scale = (span * 2) / mag;
  if (kind === "ray") return [a, [a[0] + dx * scale, a[1] + dy * scale, (a[2] || 0) + dz * scale]];
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  const mz = ((a[2] || 0) + (b[2] || 0)) / 2;
  return [
    [mx - dx * scale, my - dy * scale, mz - dz * scale],
    [mx + dx * scale, my + dy * scale, mz + dz * scale],
  ];
}

function segment3d(THREE, a, b, color) {
  const geo = new THREE.BufferGeometry().setFromPoints([toThree(THREE, a), toThree(THREE, b)]);
  return new THREE.Line(geo, new THREE.LineBasicMaterial({ color }));
}

function strip3d(THREE, points, color, close) {
  const pts = points.map((point) => toThree(THREE, point));
  if (close && pts.length) pts.push(pts[0]);
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  return new THREE.Line(geo, new THREE.LineBasicMaterial({ color }));
}

function fanMesh(THREE, points, color, opacity) {
  if (!points || points.length < 3) return new THREE.Group();
  const positions = [];
  for (let i = 1; i < points.length - 1; i++) {
    for (const point of [points[0], points[i], points[i + 1]]) {
      const v = toThree(THREE, point);
      positions.push(v.x, v.y, v.z);
    }
  }
  return meshFromPositions(THREE, positions, color, opacity);
}

function circleFill(THREE, obj, color, opacity) {
  const samples = obj.samples || [];
  const positions = [];
  const c = toThree(THREE, obj.center);
  for (let i = 0; i < samples.length; i++) {
    const a = toThree(THREE, samples[i]);
    const b = toThree(THREE, samples[(i + 1) % samples.length]);
    positions.push(c.x, c.y, c.z, a.x, a.y, a.z, b.x, b.y, b.z);
  }
  return meshFromPositions(THREE, positions, color, opacity);
}

function polyMesh(THREE, obj, color) {
  const positions = [];
  const verts = obj.vertices || [];
  for (const face of obj.faces || []) {
    for (let i = 1; i < face.length - 1; i++) {
      for (const index of [face[0], face[i], face[i + 1]]) {
        const v = toThree(THREE, verts[index]);
        positions.push(v.x, v.y, v.z);
      }
    }
  }
  return meshFromPositions(THREE, positions, colorFrom(obj.style && obj.style.fill, color), opacityOf(obj, obj.style && obj.style.fill));
}

function edgeMesh(THREE, obj, color) {
  const verts = obj.vertices || [];
  const seen = new Set();
  const points = [];
  for (const face of obj.faces || []) {
    for (let i = 0; i < face.length; i++) {
      const a = face[i];
      const b = face[(i + 1) % face.length];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key)) continue;
      seen.add(key);
      points.push(toThree(THREE, verts[a]), toThree(THREE, verts[b]));
    }
  }
  const geo = new THREE.BufferGeometry().setFromPoints(points);
  return new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color }));
}

function meshFromPositions(THREE, positions, color, opacity) {
  if (!positions.length) return new THREE.Group();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.55,
    metalness: 0,
    side: THREE.DoubleSide,
    transparent: opacity < 0.999,
    opacity,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  return new THREE.Mesh(geo, material);
}

function surfaceMaterial(THREE, obj, fallback) {
  return new THREE.MeshStandardMaterial({
    color: colorFrom(obj.style && obj.style.fill, fallback),
    roughness: 0.5,
    metalness: 0,
    side: THREE.DoubleSide,
    transparent: opacityOf(obj, obj.style && obj.style.fill) < 0.999,
    opacity: opacityOf(obj, obj.style && obj.style.fill),
  });
}

function colorFrom(fill, fallback) {
  if (!fill || fill === "none") return fallback;
  return new gfx.THREE.Color(`#${String(fill).replace("#", "").slice(0, 6)}`);
}

function opacityOf(obj, fill) {
  if (obj.style && obj.style.opacity != null) return obj.style.opacity;
  if (fill && String(fill).replace("#", "").length === 8) {
    return parseInt(String(fill).replace("#", "").slice(6), 16) / 255;
  }
  return 1;
}

function labelMeta(obj) {
  if (obj.type === "point") return { kind: "point" };
  if (obj.a && obj.b) return { kind: "segment", a: obj.a, b: obj.b };
  return { kind: "note" };
}

function tag(THREE, at, label, meta) {
  const holder = document.createElement("div");
  const text = document.createElement("span");
  text.className = "tag-text";
  text.textContent = label;
  holder.appendChild(text);
  const object = new gfx.CSS2DObject(holder);
  object.position.copy(toThree(THREE, at));
  object.userData.labelMeta = meta || { kind: "note" };
  return object;
}

function placeMarks() {
  const width = view3d.clientWidth;
  const height = view3d.clientHeight;
  if (width < 2 || height < 2) return;
  const project = (point) => {
    const vector = toThree(gfx.THREE, point).project(gfx.camera);
    return [(vector.x * 0.5 + 0.5) * width, (-vector.y * 0.5 + 0.5) * height];
  };
  for (const child of gfx.content.children) {
    if (!child.isCSS2DObject) continue;
    const span = child.element.querySelector(".tag-text");
    const meta = child.userData.labelMeta || {};
    if (!span) continue;
    if (meta.kind === "segment") {
      const a = project(meta.a);
      const b = project(meta.b);
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const length = Math.hypot(dx, dy) || 1;
      let px = -dy / length;
      let py = dx / length;
      const midX = (a[0] + b[0]) / 2;
      const midY = (a[1] + b[1]) / 2;
      const towardCenterX = width / 2 - midX;
      const towardCenterY = height / 2 - midY;
      if (px * towardCenterX + py * towardCenterY > 0) {
        px = -px;
        py = -py;
      }
      span.style.transform = `translate(${px * 16}px, ${py * 16}px)`;
    } else if (meta.kind === "point") {
      span.style.transform = "translate(9px, -12px)";
    } else {
      span.style.transform = "translate(0px, -14px)";
    }
  }
}

async function ensureThree() {
  if (gfx.ready || gfx.failed) return;
  const THREE = await import("three");
  const { OrbitControls } = await import("three/addons/controls/OrbitControls.js");
  const { CSS2DRenderer, CSS2DObject } = await import("three/addons/renderers/CSS2DRenderer.js");
  gfx.THREE = THREE;
  gfx.CSS2DObject = CSS2DObject;
  gfx.scene = new THREE.Scene();
  gfx.content = new THREE.Group();
  gfx.scene.add(gfx.content);
  gfx.scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.95);
  sun.position.set(8, 12, 6);
  gfx.scene.add(sun);
  gfx.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  gfx.camera.up.set(0, 1, 0);
  gfx.renderer = new THREE.WebGLRenderer({ antialias: true });
  if ("SRGBColorSpace" in THREE) gfx.renderer.outputColorSpace = THREE.SRGBColorSpace;
  gfx.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  view3d.appendChild(gfx.renderer.domElement);
  gfx.labels = new CSS2DRenderer();
  gfx.labels.domElement.style.position = "absolute";
  gfx.labels.domElement.style.inset = "0";
  gfx.labels.domElement.style.pointerEvents = "none";
  view3d.appendChild(gfx.labels.domElement);
  gfx.controls = new OrbitControls(gfx.camera, gfx.renderer.domElement);
  gfx.controls.addEventListener("change", renderFrame);
  if (state.syncControls) state.syncControls();
  gfx.ready = true;
  new ResizeObserver(() => resize3d()).observe(view3d);
}

function clearContent() {
  for (const child of [...gfx.content.children]) {
    gfx.content.remove(child);
    dispose(child);
  }
}

function dispose(object) {
  if (object.geometry) object.geometry.dispose();
  if (object.material) {
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) material.dispose();
  }
  if (object.element) object.element.remove();
}

function resize3d() {
  if (!gfx.ready || view3d.hidden) return;
  const rect = view3d.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return;
  gfx.camera.aspect = rect.width / rect.height;
  gfx.renderer.setSize(rect.width, rect.height);
  gfx.labels.setSize(rect.width, rect.height);
  renderFrame();
}

function renderFrame() {
  if (!gfx.ready) return;
  const distance = gfx.camera.position.distanceTo(gfx.controls.target);
  gfx.camera.near = Math.max(0.01, distance / 200);
  gfx.camera.far = Math.max(100, distance * 50);
  gfx.camera.updateProjectionMatrix();
  gfx.renderer.render(gfx.scene, gfx.camera);
  placeMarks();
  gfx.labels.render(gfx.scene, gfx.camera);
}

async function poll() {
  if (state.suppressPoll) return;
  try {
    const response = await fetch("/scene", { cache: "no-store" });
    const text = await response.text();
    if (text === state.raw) return;
    let scene;
    try {
      scene = JSON.parse(text);
    } catch {
      return;
    }
    state.raw = text;
    state.scene = scene;
    await render();
  } catch {
    hint.textContent = "Waiting for the scene.";
  }
}

import { initDraw } from "./draw.js";

initDraw({ state, svg, view3d, hint, gfx, clientToMath, draw2d, render, unitsPerPx });

poll();
setInterval(poll, 400);
window.addEventListener("resize", () => {
  if (!state.scene) return;
  if (state.scene.view && state.scene.view.mode === "3d") resize3d();
  else draw2d(state.scene);
});
